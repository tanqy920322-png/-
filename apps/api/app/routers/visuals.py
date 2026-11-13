"""Photo stand-ins for the customer, and hand-marked simplified plans for the engineer."""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from typing import Annotated

from app.constants import IMAGE_EXTENSIONS, MAX_UPLOAD_BYTES
from app.deps import ActorDep, AdminDep, CustomerDep, Db
from app.models import Asset, CustomerSelection, PlanMark, PlanSheet, UnitType, VisualSubstitute
from app.services.access import load_readable_selection
from app.services.delivery_requirements import DELIVERY_REQUIREMENTS
from app.services.files import content_type_for, safe_filename
from app.services.ids import new_id
from app.services.image_to_3d import PLACEABLE_PARTS, default_size_mm
from app.services.placement import MARK_PARTS, plan_dict, remove_asset
from app.services.plan_geometry import parse_dxf, parse_svg
from app.services.serialize import selection_dict
from app.services.storage import get_storage

router = APIRouter(tags=["visuals"])

PLAN_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".dxf"}


class MeasureInput(BaseModel):
    scale_m_per_unit: float | None = None
    wall_height_m: float | None = None


class MarkInput(BaseModel):
    room_name: str = Field(min_length=1, max_length=40)
    part_id: str
    slot_label: str = ""
    x: float
    y: float


def _extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return "." + filename.lower().rsplit(".", 1)[-1]


def _read_upload(file: UploadFile, allowed: set[str], label: str) -> tuple[str, bytes, str]:
    filename = safe_filename(file.filename or "file")
    extension = _extension(filename)
    if extension not in allowed:
        raise HTTPException(status_code=400, detail=label)
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件是空的")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="文件超过 25MB")
    return filename, data, extension


def _clamp_mm(value: int | None, fallback: int) -> int:
    if value is None:
        return fallback
    if value < 10 or value > 6000:
        raise HTTPException(status_code=400, detail="尺寸请填 10 到 6000 毫米")
    return int(value)


def _store_effect_photo(
    db: Db,
    selection: CustomerSelection,
    filename: str,
    data: bytes,
    content_type: str,
) -> Asset:
    asset = Asset(
        id=new_id("asset"),
        project_id=selection.project_id,
        unit_type_id=None,
        selection_id=selection.id,
        kind="effect_photo",
        filename=filename,
        content_type=content_type,
        byte_size=len(data),
        status="stored",
        note="客户上传的效果照片。仅用于效果展示，不列入采购。",
    )
    asset.storage_key = f"assets/effect/{selection.id}/{asset.id}-{filename}"
    get_storage().put(asset.storage_key, data, content_type)
    db.add(asset)
    db.flush()
    return asset


def _preview_path(project_id: str, plan_id: str) -> str:
    return f"/api/admin/projects/{project_id}/plans/{plan_id}/file"


def _activate(db: Db, plan: PlanSheet) -> None:
    others = db.scalars(
        select(PlanSheet).where(PlanSheet.unit_type_id == plan.unit_type_id, PlanSheet.id != plan.id)
    ).all()
    for other in others:
        other.active = False
    plan.active = True


@router.get("/api/admin/delivery-requirements")
def delivery_requirements(admin: AdminDep):
    del admin
    return DELIVERY_REQUIREMENTS


@router.post("/api/selections/{selection_id}/substitutes")
def create_substitute(
    selection_id: str,
    customer: CustomerDep,
    db: Db,
    part_id: Annotated[str, Form()],
    room_name: Annotated[str, Form()],
    slot_label: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    file_extra: Annotated[UploadFile | None, File()] = None,
    width_mm: Annotated[int | None, Form()] = None,
    depth_mm: Annotated[int | None, Form()] = None,
    height_mm: Annotated[int | None, Form()] = None,
):
    selection = load_readable_selection(db, selection_id, {"role": "customer", "sub": customer.id})
    part = part_id.strip()
    if part not in PLACEABLE_PARTS:
        raise HTTPException(status_code=400, detail="这个品类不能做照片效果。请选洁具、沙发、开关插座等可摆放的件。")
    room = room_name.strip()[:40]
    slot = slot_label.strip()[:40]
    if not room or not slot:
        raise HTTPException(status_code=400, detail="请确认房间和这一件的名称")
    filename, data, _extension_name = _read_upload(file, IMAGE_EXTENSIONS, "请上传 PNG、JPG 或 WEBP 图片")
    extra_name = ""
    extra_data = b""
    if file_extra is not None and (file_extra.filename or ""):
        extra_name, extra_data, _extra_ext = _read_upload(file_extra, IMAGE_EXTENSIONS, "第二张也请用 PNG、JPG 或 WEBP")
    fallback = default_size_mm(part, slot)
    width = _clamp_mm(width_mm, fallback[0])
    depth = _clamp_mm(depth_mm, fallback[1])
    height = _clamp_mm(height_mm, fallback[2])
    existing = db.scalar(
        select(VisualSubstitute).where(
            VisualSubstitute.selection_id == selection.id,
            VisualSubstitute.part_id == part,
            VisualSubstitute.room_name == room,
            VisualSubstitute.slot_label == slot,
        )
    )
    primary = _store_effect_photo(db, selection, filename, data, content_type_for(filename, file.content_type or "image/jpeg"))
    secondary = None
    if extra_data:
        secondary = _store_effect_photo(
            db,
            selection,
            extra_name,
            extra_data,
            content_type_for(extra_name, file_extra.content_type if file_extra else "image/jpeg"),
        )
    if existing is None:
        existing = VisualSubstitute(
            id=new_id("sub"),
            selection_id=selection.id,
            part_id=part,
            room_name=room,
            slot_label=slot,
            primary_asset_id=primary.id,
        )
        db.add(existing)
    else:
        previous_primary = existing.primary_asset_id
        previous_secondary = existing.secondary_asset_id
        existing.primary_asset_id = primary.id
        existing.secondary_asset_id = None
        db.flush()
        remove_asset(db, previous_primary)
        remove_asset(db, previous_secondary)
    existing.part_id = part
    existing.room_name = room
    existing.slot_label = slot
    existing.width_mm = width
    existing.depth_mm = depth
    existing.height_mm = height
    existing.primary_asset_id = primary.id
    existing.secondary_asset_id = None if secondary is None else secondary.id
    existing.demo = False
    db.flush()
    db.expire(selection)
    return selection_dict(db, selection)


@router.delete("/api/selections/{selection_id}/substitutes/{substitute_id}")
def delete_substitute(selection_id: str, substitute_id: str, customer: CustomerDep, db: Db):
    selection = load_readable_selection(db, selection_id, {"role": "customer", "sub": customer.id})
    row = db.get(VisualSubstitute, substitute_id)
    if row is None or row.selection_id != selection.id:
        raise HTTPException(status_code=404, detail="没有这张效果照片")
    primary = row.primary_asset_id
    secondary = row.secondary_asset_id
    db.delete(row)
    db.flush()
    remove_asset(db, primary)
    remove_asset(db, secondary)
    db.flush()
    db.expire(selection)
    return selection_dict(db, selection)


def _photo_response(asset: Asset | None) -> Response:
    if asset is None or not asset.storage_key:
        raise HTTPException(status_code=404, detail="照片不存在")
    try:
        data, content_type = get_storage().get(asset.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="照片不存在") from exc
    return Response(
        content=data,
        media_type=content_type or asset.content_type,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/api/selections/{selection_id}/substitutes/{substitute_id}/photo")
def substitute_photo(selection_id: str, substitute_id: str, actor: ActorDep, db: Db, index: int = 1):
    selection = load_readable_selection(db, selection_id, actor)
    row = db.get(VisualSubstitute, substitute_id)
    if row is None or row.selection_id != selection.id:
        raise HTTPException(status_code=404, detail="照片不存在")
    asset_id = row.secondary_asset_id if index == 2 else row.primary_asset_id
    return _photo_response(db.get(Asset, asset_id))


@router.get("/api/admin/projects/{project_id}/plans")
def list_plans(project_id: str, admin: AdminDep, db: Db, unit_type_id: str | None = None):
    del admin
    stmt = select(PlanSheet).where(PlanSheet.project_id == project_id).order_by(PlanSheet.created_at.desc())
    if unit_type_id:
        stmt = stmt.where(PlanSheet.unit_type_id == unit_type_id)
    rows = db.scalars(stmt).all()
    return [plan_dict(db, row, preview_path=_preview_path(project_id, row.id)) for row in rows]


@router.post("/api/admin/projects/{project_id}/plans")
def upload_plan(
    project_id: str,
    admin: AdminDep,
    db: Db,
    unit_type_id: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    note: Annotated[str, Form()] = "",
):
    del admin
    unit = db.get(UnitType, unit_type_id)
    if unit is None or unit.project_id != project_id:
        raise HTTPException(status_code=400, detail="户型不属于该项目")
    filename, data, extension = _read_upload(
        file,
        PLAN_EXTENSIONS,
        "简化平面请用 PDF、图片、SVG 或 DXF",
    )
    vectors: list = []
    if extension == ".svg":
        media = "svg"
        vectors = parse_svg(data.decode("utf-8", errors="replace"))
        stored_note = note.strip() or "已保存 SVG，并抽出墙线轮廓。请在图上点选房间和部位。"
    elif extension == ".dxf":
        media = "dxf"
        vectors, status = parse_dxf(data)
        if status == "ok":
            stored_note = note.strip() or "已从 DXF 抽出线段。整张 DWG 分层这一轮不解析。请在图上点选。"
        elif status == "binary":
            stored_note = note.strip() or "这是二进制 DXF，没有抽出线段。请换 ASCII DXF、SVG 或图片，再点选。"
        else:
            stored_note = note.strip() or "这张 DXF 没有读出线段。请换 SVG、图片，或在空白底上点选。"
    elif extension == ".pdf":
        media = "pdf"
        stored_note = note.strip() or "PDF 已保存。这一轮不把 PDF 转成底图，请在空白底上点选，或改传图片、SVG、DXF。"
    else:
        media = "image"
        stored_note = note.strip() or "图片已保存。图片本身不生成墙线，点选仍然有效，系统按点摆放。"
    asset = Asset(
        id=new_id("asset"),
        project_id=project_id,
        unit_type_id=unit.id,
        kind="simplified_plan",
        filename=filename,
        content_type=content_type_for(filename, file.content_type or "application/octet-stream"),
        byte_size=len(data),
        status="stored",
        note=stored_note,
    )
    asset.storage_key = f"assets/plans/{asset.id}/{filename}"
    get_storage().put(asset.storage_key, data, asset.content_type)
    db.add(asset)
    db.flush()
    plan = PlanSheet(
        id=new_id("plan"),
        project_id=project_id,
        unit_type_id=unit.id,
        asset_id=asset.id,
        filename=filename,
        media=media,
        vectors=vectors,
        active=False,
        note=stored_note,
    )
    db.add(plan)
    db.flush()
    _activate(db, plan)
    db.flush()
    return plan_dict(db, plan, preview_path=_preview_path(project_id, plan.id))


@router.post("/api/admin/projects/{project_id}/plans/{plan_id}/activate")
def activate_plan(project_id: str, plan_id: str, admin: AdminDep, db: Db):
    del admin
    plan = db.get(PlanSheet, plan_id)
    if plan is None or plan.project_id != project_id:
        raise HTTPException(status_code=404, detail="没有这张简化平面")
    _activate(db, plan)
    db.flush()
    return plan_dict(db, plan, preview_path=_preview_path(project_id, plan.id))


@router.put("/api/admin/projects/{project_id}/plans/{plan_id}/measure")
def set_plan_measure(project_id: str, plan_id: str, body: MeasureInput, admin: AdminDep, db: Db):
    """Record a scale or storey height the drawing already states. Blank stays blank."""
    del admin
    plan = db.get(PlanSheet, plan_id)
    if plan is None or plan.project_id != project_id:
        raise HTTPException(status_code=404, detail="没有这张简化平面")
    if body.scale_m_per_unit is not None and body.scale_m_per_unit <= 0:
        raise HTTPException(status_code=400, detail="比例要大于 0。图纸没写比例就留空，不要填估计值。")
    if body.wall_height_m is not None and body.wall_height_m <= 0:
        raise HTTPException(status_code=400, detail="层高要大于 0。图纸没写层高就留空，不要填估计值。")
    plan.scale_m_per_unit = body.scale_m_per_unit
    plan.wall_height_m = body.wall_height_m
    db.flush()
    return plan_dict(db, plan, preview_path=_preview_path(project_id, plan.id))


@router.post("/api/admin/projects/{project_id}/plans/{plan_id}/marks")
def add_mark(project_id: str, plan_id: str, body: MarkInput, admin: AdminDep, db: Db):
    del admin
    plan = db.get(PlanSheet, plan_id)
    if plan is None or plan.project_id != project_id:
        raise HTTPException(status_code=404, detail="没有这张简化平面")
    if body.part_id not in MARK_PARTS:
        raise HTTPException(status_code=400, detail="请选择天花、墙面、地面，或马桶、沙发、开关等可摆放的部位")
    if not 0 <= body.x <= 1 or not 0 <= body.y <= 1:
        raise HTTPException(status_code=400, detail="点选位置要落在图内")
    mark = PlanMark(
        id=new_id("mark"),
        plan_id=plan.id,
        project_id=plan.project_id,
        unit_type_id=plan.unit_type_id,
        room_name=body.room_name.strip()[:40],
        part_id=body.part_id,
        slot_label=(body.slot_label or "").strip()[:40],
        x=round(body.x, 4),
        y=round(body.y, 4),
    )
    db.add(mark)
    db.flush()
    db.expire(plan, ["marks"])
    return plan_dict(db, plan, preview_path=_preview_path(project_id, plan.id))


@router.delete("/api/admin/projects/{project_id}/plans/{plan_id}/marks/{mark_id}")
def delete_mark(project_id: str, plan_id: str, mark_id: str, admin: AdminDep, db: Db):
    del admin
    plan = db.get(PlanSheet, plan_id)
    mark = db.get(PlanMark, mark_id)
    if plan is None or mark is None or mark.plan_id != plan.id or plan.project_id != project_id:
        raise HTTPException(status_code=404, detail="没有这个点")
    db.delete(mark)
    db.flush()
    db.expire(plan, ["marks"])
    return plan_dict(db, plan, preview_path=_preview_path(project_id, plan.id))


@router.get("/api/admin/projects/{project_id}/plans/{plan_id}/file")
def plan_file(project_id: str, plan_id: str, admin: AdminDep, db: Db):
    del admin
    plan = db.get(PlanSheet, plan_id)
    if plan is None or plan.project_id != project_id:
        raise HTTPException(status_code=404, detail="没有这张简化平面")
    asset = db.get(Asset, plan.asset_id)
    return _photo_response(asset)
