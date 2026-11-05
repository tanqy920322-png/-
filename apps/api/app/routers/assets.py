from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy import select

from app.deps import ActorDep, Db
from app.models import Asset, CustomerSelection
from app.services.files import attachment_headers
from app.services.storage import get_storage

router = APIRouter(prefix="/api/assets", tags=["assets"])


def _can_read(db: Db, asset: Asset, actor: dict) -> bool:
    if actor.get("role") == "admin":
        return True
    if actor.get("role") != "customer":
        return False
    if asset.selection_id:
        selection = db.get(CustomerSelection, asset.selection_id)
        if selection is not None and selection.customer_id == actor.get("sub"):
            return True
    return (
        db.scalar(
            select(CustomerSelection.id).where(
                CustomerSelection.customer_id == actor.get("sub"),
                CustomerSelection.project_id == asset.project_id,
            )
        )
        is not None
    )


@router.get("/{asset_id}/file")
def download_asset(asset_id: str, actor: ActorDep, db: Db):
    asset = db.get(Asset, asset_id)
    if asset is None or not _can_read(db, asset, actor):
        raise HTTPException(status_code=404, detail="文件不存在")
    if asset.status != "stored" or not asset.storage_key:
        raise HTTPException(status_code=404, detail="图纸尚未上传，当前为占位记录")
    try:
        data, content_type = get_storage().get(asset.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="文件内容缺失") from exc
    return Response(
        content=data,
        media_type=content_type or asset.content_type,
        headers=attachment_headers(asset.filename),
    )
