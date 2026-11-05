from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import CustomerSelection


def load_readable_selection(db: Session, selection_id: str, actor: dict) -> CustomerSelection:
    selection = db.get(CustomerSelection, selection_id)
    if selection is None:
        raise HTTPException(status_code=404, detail="方案不存在")
    if actor.get("role") == "admin":
        return selection
    if actor.get("role") == "customer" and actor.get("sub") == selection.customer_id:
        return selection
    raise HTTPException(status_code=404, detail="方案不存在")
