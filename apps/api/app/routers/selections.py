from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import ActorDep, CustomerDep, Db
from app.models import CustomerSelection, Project, Scheme, Style, UnitType
from app.services.access import load_readable_selection
from app.services.ids import new_id
from app.services.serialize import selection_dict, selection_list_item

router = APIRouter(prefix="/api/selections", tags=["selections"])


class SelectionCreate(BaseModel):
    project_code: str
    unit_type_id: str


class SelectionUpdate(BaseModel):
    style_id: str | None = None
    ceiling_scheme_id: str | None = None
    floor_scheme_id: str | None = None
    wall_scheme_id: str | None = None


def _touch(selection: CustomerSelection) -> None:
    selection.updated_at = datetime.now(timezone.utc)


def _apply_update(db: Db, selection: CustomerSelection, body: SelectionUpdate) -> None:
    changed = False
    if body.style_id is not None and body.style_id != selection.style_id:
        style = db.get(Style, body.style_id)
        if style is None:
            raise HTTPException(status_code=400, detail="风格不存在")
        selection.style_id = style.id
        for part_id, attr in (
            ("ceiling", "ceiling_scheme_id"),
            ("floor", "floor_scheme_id"),
            ("wall", "wall_scheme_id"),
        ):
            scheme = db.scalar(
                select(Scheme).where(
                    Scheme.style_id == style.id,
                    Scheme.part_id == part_id,
                    Scheme.scheme_index == 1,
                )
            )
            if scheme is None:
                raise HTTPException(status_code=400, detail="该风格缺少默认方案")
            setattr(selection, attr, scheme.id)
        changed = True
    scheme_updates = (
        ("ceiling", body.ceiling_scheme_id, "ceiling_scheme_id"),
        ("floor", body.floor_scheme_id, "floor_scheme_id"),
        ("wall", body.wall_scheme_id, "wall_scheme_id"),
    )
    if any(item[1] for item in scheme_updates):
        if selection.style_id is None:
            raise HTTPException(status_code=400, detail="请先选择风格")
        for part_id, incoming, attr in scheme_updates:
            if not incoming:
                continue
            scheme = db.get(Scheme, incoming)
            if scheme is None or scheme.style_id != selection.style_id or scheme.part_id != part_id:
                raise HTTPException(status_code=400, detail="方案与当前风格或部位不匹配")
            setattr(selection, attr, scheme.id)
            changed = True
    if changed:
        if selection.status == "submitted":
            selection.status = "draft"
        _touch(selection)


@router.get("/mine")
def mine(customer: CustomerDep, db: Db):
    rows = db.scalars(
        select(CustomerSelection)
        .where(CustomerSelection.customer_id == customer.id)
        .order_by(CustomerSelection.updated_at.desc())
    ).all()
    return [selection_list_item(db, row) for row in rows]


@router.post("")
def create_selection(body: SelectionCreate, customer: CustomerDep, db: Db):
    code = body.project_code.strip().upper()
    project = db.scalar(select(Project).where(Project.code == code, Project.status == "published"))
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在或尚未发布")
    unit = db.get(UnitType, body.unit_type_id)
    if unit is None or unit.project_id != project.id:
        raise HTTPException(status_code=404, detail="户型不存在")
    existing = db.scalar(
        select(CustomerSelection).where(
            CustomerSelection.customer_id == customer.id,
            CustomerSelection.unit_type_id == unit.id,
        )
    )
    if existing is not None:
        return selection_dict(db, existing)
    selection = CustomerSelection(
        id=new_id("sel"),
        customer_id=customer.id,
        project_id=project.id,
        unit_type_id=unit.id,
        status="draft",
    )
    db.add(selection)
    db.flush()
    db.expire(selection)
    return selection_dict(db, selection)


@router.get("/{selection_id}")
def get_selection(selection_id: str, actor: ActorDep, db: Db):
    selection = load_readable_selection(db, selection_id, actor)
    return selection_dict(db, selection)


@router.patch("/{selection_id}")
def update_selection(selection_id: str, body: SelectionUpdate, customer: CustomerDep, db: Db):
    selection = load_readable_selection(db, selection_id, {"role": "customer", "sub": customer.id})
    _apply_update(db, selection, body)
    db.flush()
    db.expire(selection)
    return selection_dict(db, selection)


@router.post("/{selection_id}/submit")
def submit_selection(selection_id: str, customer: CustomerDep, db: Db):
    selection = load_readable_selection(db, selection_id, {"role": "customer", "sub": customer.id})
    if not (selection.style_id and selection.ceiling_scheme_id and selection.floor_scheme_id and selection.wall_scheme_id):
        raise HTTPException(status_code=400, detail="请先选好风格和天花、地面、墙面")
    selection.status = "submitted"
    _touch(selection)
    db.flush()
    db.expire(selection)
    return selection_dict(db, selection)
