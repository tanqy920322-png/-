from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import ActorDep, Db
from app.models import ExportArtifact
from app.services.access import load_readable_selection
from app.services.files import attachment_headers
from app.services.ids import new_id
from app.services.pack import render_image_pack
from app.services.pdf import render_quote_pdf
from app.services.serialize import selection_dict
from app.services.storage import get_storage

router = APIRouter(tags=["exports"])


class ExportCreate(BaseModel):
    kind: str


def _owns_export(db: Db, artifact: ExportArtifact, actor: dict) -> bool:
    try:
        load_readable_selection(db, artifact.selection_id, actor)
    except HTTPException:
        return False
    return True


@router.post("/api/selections/{selection_id}/exports")
def create_export(selection_id: str, body: ExportCreate, actor: ActorDep, db: Db):
    if body.kind not in {"quote_pdf", "image_pack"}:
        raise HTTPException(status_code=400, detail="仅支持报价 PDF 或图册占位包")
    selection = load_readable_selection(db, selection_id, actor)
    detail = selection_dict(db, selection)
    project_code = detail["project"]["code"]
    unit_code = detail["unit"]["code"]
    if body.kind == "quote_pdf":
        data = render_quote_pdf(detail)
        filename = f"报价单-{project_code}-{unit_code}.pdf"
        content_type = "application/pdf"
    else:
        data = render_image_pack(detail)
        filename = f"图册占位-{project_code}-{unit_code}.zip"
        content_type = "application/zip"
    artifact = ExportArtifact(
        id=new_id("exp"),
        selection_id=selection.id,
        kind=body.kind,
        filename=filename,
        content_type=content_type,
        storage_key=f"exports/{selection.id}/{new_id('file')}-{filename}",
        status="ready",
    )
    get_storage().put(artifact.storage_key, data, content_type)
    db.add(artifact)
    db.flush()
    return {
        "id": artifact.id,
        "kind": artifact.kind,
        "filename": artifact.filename,
        "content_type": artifact.content_type,
        "status": artifact.status,
    }


@router.get("/api/exports/{export_id}/file")
def download_export(export_id: str, actor: ActorDep, db: Db):
    artifact = db.get(ExportArtifact, export_id)
    if artifact is None or not _owns_export(db, artifact, actor):
        raise HTTPException(status_code=404, detail="导出文件不存在")
    try:
        data, content_type = get_storage().get(artifact.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="导出文件内容缺失") from exc
    return Response(
        content=data,
        media_type=content_type or artifact.content_type,
        headers=attachment_headers(artifact.filename),
    )


@router.get("/api/selections/{selection_id}/exports")
def list_exports(selection_id: str, actor: ActorDep, db: Db):
    load_readable_selection(db, selection_id, actor)
    rows = db.scalars(
        select(ExportArtifact)
        .where(ExportArtifact.selection_id == selection_id)
        .order_by(ExportArtifact.created_at.desc())
    ).all()
    return [
        {
            "id": row.id,
            "kind": row.kind,
            "filename": row.filename,
            "content_type": row.content_type,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
