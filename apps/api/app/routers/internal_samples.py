"""Internal samples, confirmed generated meshes, and the quota-blocked generation desk.

Starting a job records the upload and stops. It does not call a paid provider.
"""

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.constants import CATEGORY_LABELS
from app.deps import AdminDep, Db
from app.models import GeneratedCandidate, InternalSample, WorkerJob
from app.services.ids import new_id
from app.services.image_to_3d import blocked_generation_result
from app.services.internal_catalog import (
    DISCLAIMER,
    confirm_candidate,
    generation_status,
    image_path,
    list_samples,
    resolve_mesh,
    sample_dict,
    texture_catalog,
)
from app.services.storage import get_storage

ACCEPTED_UPLOADS = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".zip"}
MAX_GENERATION_UPLOAD = 20 * 1024 * 1024

router = APIRouter(tags=["internal-samples"])


def _file_response(path) -> Response:
    data = path.read_bytes()
    media = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return Response(content=data, media_type=media, headers={"Cache-Control": "public, max-age=3600"})


@router.get("/api/admin/internal-samples")
def admin_samples(admin: AdminDep, db: Db):
    del admin
    rows = [sample_dict(row) for row in list_samples(db)]
    pack = [row for row in rows if row["source"] == "sample_pack"]
    generated = [row for row in rows if row["source"] == "generated"]
    return {
        "disclaimer": DISCLAIMER,
        "count": len(rows),
        "pack_count": len(pack),
        "verified_count": sum(1 for row in pack if row["verified"]),
        "generated_count": len(generated),
        "items": rows,
    }


@router.get("/api/admin/internal-samples/{sample_id}/image")
def admin_sample_image(sample_id: str, admin: AdminDep, db: Db):
    del admin
    row = db.get(InternalSample, sample_id)
    if row is None:
        raise HTTPException(status_code=404, detail="没有这条内部样板")
    path = image_path(row)
    if path is None:
        if row.source == "generated":
            raise HTTPException(status_code=404, detail="这件生成件的预览图没有放进仓库。页面上的其他记录不受影响。")
        raise HTTPException(status_code=404, detail="这条没有官方单品图，不另配图")
    return _file_response(path)


@router.get("/api/admin/internal-samples/{sample_id}/mesh")
def admin_sample_mesh(sample_id: str, admin: AdminDep, db: Db):
    del admin
    row = db.get(InternalSample, sample_id)
    if row is None or row.source != "generated" or not row.model_code:
        raise HTTPException(status_code=404, detail="这条没有生成网格。评测资料包本身不带三维文件。")
    filename = f"{row.model_code}.glb"
    path, note = resolve_mesh(filename)
    if path is None:
        raise HTTPException(status_code=404, detail=note)
    try:
        data = path.read_bytes()
    except OSError:
        raise HTTPException(status_code=404, detail=note) from None
    return Response(
        content=data,
        media_type="model/gltf-binary",
        headers={"Cache-Control": "private, no-cache", "Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/api/finish-textures")
def finish_textures(db: Db):
    return texture_catalog(db)


@router.get("/api/finish-textures/{sample_id}/image")
def finish_texture_image(sample_id: str, db: Db):
    row = db.get(InternalSample, sample_id)
    if row is None or row.kind != "material" or row.source != "sample_pack":
        raise HTTPException(status_code=404, detail="没有这张示意贴图")
    path = image_path(row)
    if path is None:
        raise HTTPException(status_code=404, detail="没有这张示意贴图")
    return _file_response(path)


@router.get("/api/admin/generation")
def generation(admin: AdminDep, db: Db):
    del admin
    return generation_status(db)


@router.post("/api/admin/generation/start")
async def start_generation(
    admin: AdminDep,
    db: Db,
    file: UploadFile = File(...),
    part_id: str = Form(""),
    brand: str = Form(""),
    model_code: str = Form(""),
    name: str = Form(""),
):
    """Accept a catalog or product image and stop. Free quota is gone; post-paid stays off."""
    del admin
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ACCEPTED_UPLOADS:
        raise HTTPException(status_code=400, detail="生模入口只接收图册（PDF、ZIP）或产品图（PNG、JPG、WEBP）。")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件是空的，没有可发起的图。")
    if len(data) > MAX_GENERATION_UPLOAD:
        raise HTTPException(status_code=400, detail="文件过大。生模入口只留一份本地记录，不把文件交给付费服务。")
    part = (part_id or "").strip()
    if part and part not in CATEGORY_LABELS:
        raise HTTPException(status_code=400, detail="没有这个品类。")
    outcome = blocked_generation_result()
    job_id = new_id("job")
    stored = f"generation-inbox/{job_id}{suffix}"
    get_storage().put(stored, data, file.content_type or "application/octet-stream")
    job = WorkerJob(
        id=job_id,
        kind="image_to_3d",
        status="blocked",
        payload={
            "filename": filename[:180],
            "part_id": part,
            "brand": brand.strip()[:80],
            "model_code": model_code.strip()[:80],
            "name": name.strip()[:80],
            "bytes": len(data),
            "storage_key": stored,
        },
        result={
            "mode": "quota_exhausted",
            "paid_api_called": False,
            "postpaid_enabled": False,
            "message": outcome["message"],
        },
    )
    db.add(job)
    db.flush()
    return {
        "id": job.id,
        "status": outcome["status"],
        "paid_api_called": False,
        "postpaid_enabled": False,
        "free_pack_exhausted": True,
        "customer_visible": False,
        "priced": False,
        "orderable": False,
        "filename": filename,
        "message": outcome["message"],
    }


@router.post("/api/admin/generation/{candidate_id}/confirm")
def confirm_generated(candidate_id: str, admin: AdminDep, db: Db):
    del admin
    row = db.get(GeneratedCandidate, candidate_id)
    if row is None or row.status != "pending":
        raise HTTPException(status_code=404, detail="没有待确认的生成件")
    sample = confirm_candidate(db, row)
    return {"queue_status": "confirmed", "sample": sample_dict(sample)}


@router.post("/api/admin/generation/{candidate_id}/reject")
def reject_generated(candidate_id: str, admin: AdminDep, db: Db):
    del admin
    row = db.get(GeneratedCandidate, candidate_id)
    if row is None or row.status != "pending":
        raise HTTPException(status_code=404, detail="没有待确认的生成件")
    row.status = "rejected"
    db.flush()
    return generation_status(db)
