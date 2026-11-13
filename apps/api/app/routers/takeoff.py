"""Read-only print/review takeoff. Does not change the selection quote."""

from fastapi import APIRouter

from app.deps import ActorDep, Db
from app.services.access import load_readable_selection
from app.services.takeoff import takeoff_for_selection

router = APIRouter(tags=["takeoff"])


@router.get("/api/selections/{selection_id}/takeoff")
def read_takeoff(selection_id: str, actor: ActorDep, db: Db):
    selection = load_readable_selection(db, selection_id, actor)
    return takeoff_for_selection(db, selection)
