"""Internal sample library and the empty confirm-to-catalog queue. No generation call."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.deps import AdminDep, Db
from app.models import GeneratedCandidate, InternalSample
from app.services.internal_catalog import (
    confirm_candidate,
    generation_status,
    image_path,
    list_samples,
    sample_dict,
    texture_catalog,
)

router = APIRouter(tags=["internal-samples"])


def _file_response(path) -> Response:
    data = path.read_bytes()
    media = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return Response(content=data, media_type=media, headers={"Cache-Control": "public, max-age=3600"})


@router.get("/api/admin/internal-samples")
def admin_samples(admin: AdminDep, db: Db):
    del admin
    rows = [sample_dict(row) for row in list_samples(db)]
    return {
        "disclaimer": rows[0]["disclaimer"] if rows else "",
        "count": len(rows),
        "verified_count": sum(1 for row in rows if row["verified"]),
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
        raise HTTPException(status_code=404, detail="这条没有官方单品图，不另配图")
    return _file_response(path)


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
