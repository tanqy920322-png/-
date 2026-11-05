import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from typing import Annotated

from app.constants import IMAGE_EXTENSIONS, MAX_UPLOAD_BYTES
from app.deps import ActorDep, AdminDep, CustomerDep, Db
from app.models import Asset, CustomerSelection, WorkerJob
from app.services.access import load_readable_selection
from app.services.files import content_type_for, safe_filename
from app.services.ids import new_id
from app.services.queue import get_queue
from app.services.serialize import iso
from app.services.storage import get_storage

router = APIRouter(prefix="/api/ai", tags=["ai"])

SCENE_KEYS = ("DASHSCOPE_API_KEY", "VOLCENGINE_API_KEY")
VISION_KEYS = ("QWEN_API_KEY", "DOUBAO_API_KEY")


def _provider(keys: tuple[str, ...]) -> str:
    if any(os.getenv(key) for key in keys):
        return "key_present_adapter_missing"
    return "unconfigured"


def _job_dict(job: WorkerJob) -> dict:
    result = job.result or {}
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "selection_id": job.selection_id,
        "message": result.get("message", ""),
        "provider": result.get("provider", "unconfigured"),
        "result": result,
        "created_at": iso(job.created_at),
    }


def _enqueue(db: Db, job: WorkerJob) -> None:
    db.add(job)
    db.flush()
    get_queue().enqueue(job.id)


@router.post("/scene")
def create_scene(
    customer: CustomerDep,
    db: Db,
    selection_id: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    selection = load_readable_selection(db, selection_id, {"role": "customer", "sub": customer.id})
    filename = safe_filename(file.filename or "furniture.jpg")
    extension = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if extension not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="请上传 PNG、JPG 或 WEBP 图片")
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="图片是空的")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="图片超过 25MB")
    content_type = content_type_for(filename, file.content_type or "image/jpeg")
    asset = Asset(
        id=new_id("asset"),
        project_id=selection.project_id,
        unit_type_id=selection.unit_type_id,
        selection_id=selection.id,
        kind="furniture_photo",
        filename=filename,
        content_type=content_type,
        byte_size=len(data),
        storage_key=f"assets/scene/{selection.id}/{filename}",
        status="stored",
        note="客户上传的家具照片，供后续场景生成使用。",
    )
    # Keep the storage key unique if the same name is uploaded twice.
    asset.storage_key = f"assets/scene/{selection.id}/{asset.id}-{filename}"
    get_storage().put(asset.storage_key, data, content_type)
    db.add(asset)
    provider = _provider(SCENE_KEYS)
    message = "已保存家具照片。场景生成将接入阿里云百炼 DashScope 或火山引擎图像接口，当前返回占位任务。"
    if provider == "key_present_adapter_missing":
        message = "已保存家具照片。检测到图像接口密钥，但适配器尚未接入，本次仍返回占位结果。"
    job = WorkerJob(
        id=new_id("job"),
        kind="scene_gen",
        status="stub_completed",
        selection_id=selection.id,
        payload={"asset_id": asset.id, "providers": ["dashscope", "volcengine"]},
        result={
            "provider": provider,
            "message": message,
            "image_url": None,
            "asset_id": asset.id,
            "worker_ack": False,
        },
    )
    _enqueue(db, job)
    return _job_dict(job)


@router.post("/floorplan")
def recognize_floorplan(
    admin: AdminDep,
    db: Db,
    asset_id: Annotated[str, Form()],
):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="图纸不存在")
    provider = _provider(VISION_KEYS)
    if asset.status != "stored":
        message = "这是占位图纸，没有可识别的文件。户型识别将接入 Qwen-VL 或豆包视觉，当前返回占位结果。"
    else:
        message = "已接收图纸。户型识别将接入 Qwen-VL 或豆包视觉，当前返回占位结果，不回写房间面积。"
    if provider == "key_present_adapter_missing":
        message = "检测到视觉接口密钥，但适配器尚未接入，本次仍返回占位结果。"
    selection_id = asset.selection_id
    if selection_id is None:
        selection_id = db.scalar(
            select_first_selection(db, asset.project_id)
        )
    job = WorkerJob(
        id=new_id("job"),
        kind="floorplan_recognition",
        status="stub_completed",
        selection_id=selection_id,
        payload={"asset_id": asset.id, "providers": ["qwen-vl", "doubao"]},
        result={
            "provider": provider,
            "message": message,
            "rooms_detected": None,
            "asset_id": asset.id,
            "worker_ack": False,
        },
    )
    _enqueue(db, job)
    return _job_dict(job)


def select_first_selection(db: Db, project_id: str):
    from sqlalchemy import select

    return select(CustomerSelection.id).where(CustomerSelection.project_id == project_id).limit(1)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, actor: ActorDep, db: Db):
    job = db.get(WorkerJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if actor.get("role") == "customer":
        if not job.selection_id:
            raise HTTPException(status_code=404, detail="任务不存在")
        selection = db.get(CustomerSelection, job.selection_id)
        if selection is None or selection.customer_id != actor.get("sub"):
            raise HTTPException(status_code=404, detail="任务不存在")
    return _job_dict(job)
