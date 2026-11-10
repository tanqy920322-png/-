from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import ActorDep, CustomerDep, Db
from app.models import (
    CatalogProduct,
    CustomerSelection,
    Part,
    ProcurementItem,
    Project,
    Scheme,
    SchemeItem,
    SelectionItemPick,
    SelectionLine,
    Style,
    UnitType,
)
from app.services.access import load_readable_selection
from app.services.ids import new_id
from app.services.serialize import selection_dict, selection_list_item

router = APIRouter(prefix="/api/selections", tags=["selections"])


class SelectionCreate(BaseModel):
    project_code: str
    unit_type_id: str


class ItemPickInput(BaseModel):
    item_id: str
    included: bool = True
    quantity: float = 1
    brand_tier: str | None = None
    product_id: str | None = None


class LineInput(BaseModel):
    part_id: str
    scheme_id: str | None = None
    procurement_item_id: str | None = None
    room_or_zone: str = ""
    brand_tier: str | None = None
    quantity: float = 1
    items: list[ItemPickInput] | None = None


class SelectionUpdate(BaseModel):
    style_id: str | None = None
    ceiling_scheme_id: str | None = None
    floor_scheme_id: str | None = None
    wall_scheme_id: str | None = None
    lines: list[LineInput] | None = None


VISUAL_PARTS = ("ceiling", "floor", "wall")
BRAND_TIERS = {"domestic", "import"}


def _touch(selection: CustomerSelection) -> None:
    selection.updated_at = datetime.now(timezone.utc)


def _refresh_picks(db: Db, line: SelectionLine, explicit: list[ItemPickInput] | None, include_all: bool) -> None:
    if not line.scheme_id:
        return
    items = db.scalars(select(SchemeItem).where(SchemeItem.scheme_id == line.scheme_id).order_by(SchemeItem.sort_order)).all()
    valid_ids = {item.id for item in items}
    current = db.scalars(select(SelectionItemPick).where(SelectionItemPick.selection_line_id == line.id)).all()
    for pick in current:
        if pick.scheme_item_id not in valid_ids:
            db.delete(pick)
    db.flush()
    by_id = {row.item_id: row for row in explicit} if explicit is not None else None
    existing = {
        pick.scheme_item_id: pick
        for pick in db.scalars(select(SelectionItemPick).where(SelectionItemPick.selection_line_id == line.id)).all()
    }
    for item in items:
        spec = by_id.get(item.id) if by_id is not None else None
        pick = existing.get(item.id)
        if pick is None:
            pick = SelectionItemPick(
                id=new_id("pick"),
                selection_line_id=line.id,
                scheme_item_id=item.id,
                included=spec.included if spec else include_all,
                quantity=spec.quantity if spec else item.default_quantity,
                brand_tier=(spec.brand_tier if spec and spec.brand_tier else line.brand_tier or "domestic"),
                product_id=spec.product_id if spec and spec.product_id else None,
            )
            db.add(pick)
        elif spec is not None:
            pick.included = spec.included
            pick.quantity = spec.quantity
            pick.brand_tier = spec.brand_tier or pick.brand_tier or "domestic"
            if spec.product_id:
                pick.product_id = spec.product_id


def _upsert_line(
    db: Db,
    selection: CustomerSelection,
    *,
    part_id: str,
    scheme_id: str | None,
    procurement_item_id: str | None,
    room_or_zone: str,
    brand_tier: str | None,
    quantity: float,
    explicit_items: list[ItemPickInput] | None = None,
    include_all: bool = False,
) -> None:
    zone = (room_or_zone or "").strip()[:40]
    existing = db.scalar(
        select(SelectionLine).where(
            SelectionLine.selection_id == selection.id,
            SelectionLine.part_id == part_id,
            SelectionLine.room_or_zone == zone,
        )
    )
    if scheme_id is None and procurement_item_id is None:
        if existing is not None:
            db.delete(existing)
        if part_id in VISUAL_PARTS and zone == "":
            setattr(selection, f"{part_id}_scheme_id", None)
        return
    if existing is None:
        existing = SelectionLine(
            id=new_id("line"),
            selection_id=selection.id,
            part_id=part_id,
            room_or_zone=zone,
        )
        db.add(existing)
    existing.scheme_id = scheme_id
    existing.procurement_item_id = procurement_item_id
    existing.brand_tier = brand_tier
    existing.quantity = quantity
    if part_id in VISUAL_PARTS and zone == "":
        setattr(selection, f"{part_id}_scheme_id", scheme_id)
    db.flush()
    _refresh_picks(db, existing, explicit_items, include_all and part_id not in VISUAL_PARTS)


def _validate_line(db: Db, selection: CustomerSelection, line: LineInput) -> None:
    part = db.get(Part, line.part_id)
    if part is None:
        raise HTTPException(status_code=400, detail="部位不存在")
    if line.quantity <= 0:
        raise HTTPException(status_code=400, detail="数量需要大于 0")
    if line.brand_tier is not None and line.brand_tier not in BRAND_TIERS:
        raise HTTPException(status_code=400, detail="品牌档位只能是国产或进口")
    if line.brand_tier and not part.allows_brand_tier:
        raise HTTPException(status_code=400, detail="这个类目不区分进口和国产")
    if line.scheme_id:
        scheme = db.get(Scheme, line.scheme_id)
        if scheme is None or scheme.part_id != part.id:
            raise HTTPException(status_code=400, detail="方案与部位不匹配")
        if part.visual:
            if selection.style_id is None:
                raise HTTPException(status_code=400, detail="请先选择风格")
            if scheme.style_id != selection.style_id:
                raise HTTPException(status_code=400, detail="方案与当前风格或部位不匹配")
        elif scheme.style_id is not None:
            raise HTTPException(status_code=400, detail="这个类目不跟随风格方案")
    if line.procurement_item_id:
        item = db.get(ProcurementItem, line.procurement_item_id)
        if item is None or item.category != part.id:
            raise HTTPException(status_code=400, detail="价表物料与类目不匹配")
    if line.items and line.scheme_id:
        for pick in line.items:
            piece = db.get(SchemeItem, pick.item_id)
            if piece is None or piece.scheme_id != line.scheme_id:
                raise HTTPException(status_code=400, detail="件不属于当前方案")
            if pick.quantity <= 0:
                raise HTTPException(status_code=400, detail="数量需要大于 0")
            if pick.brand_tier is not None and pick.brand_tier not in BRAND_TIERS:
                raise HTTPException(status_code=400, detail="品牌档位只能是国产或进口")
            if pick.product_id:
                product = db.get(CatalogProduct, pick.product_id)
                piece = db.get(SchemeItem, pick.item_id)
                expected = piece.display_part_id if piece and piece.display_part_id else line.part_id
                if product is None or product.status != "confirmed" or product.part_id != expected:
                    raise HTTPException(status_code=400, detail="示例产品与这一件的品类不一致")


def _apply_update(db: Db, selection: CustomerSelection, body: SelectionUpdate) -> None:
    changed = False
    if body.style_id is not None and body.style_id != selection.style_id:
        style = db.get(Style, body.style_id)
        if style is None:
            raise HTTPException(status_code=400, detail="风格不存在")
        selection.style_id = style.id
        for part_id in VISUAL_PARTS:
            scheme = db.scalar(
                select(Scheme).where(
                    Scheme.style_id == style.id,
                    Scheme.part_id == part_id,
                    Scheme.scheme_index == 1,
                )
            )
            if scheme is None:
                raise HTTPException(status_code=400, detail="该风格缺少默认方案")
            setattr(selection, f"{part_id}_scheme_id", scheme.id)
            _upsert_line(
                db,
                selection,
                part_id=part_id,
                scheme_id=scheme.id,
                procurement_item_id=None,
                room_or_zone="",
                brand_tier=None,
                quantity=1,
            )
        changed = True
    scheme_updates = (
        ("ceiling", body.ceiling_scheme_id),
        ("floor", body.floor_scheme_id),
        ("wall", body.wall_scheme_id),
    )
    if any(item[1] for item in scheme_updates):
        if selection.style_id is None:
            raise HTTPException(status_code=400, detail="请先选择风格")
        for part_id, incoming in scheme_updates:
            if not incoming:
                continue
            scheme = db.get(Scheme, incoming)
            if scheme is None or scheme.style_id != selection.style_id or scheme.part_id != part_id:
                raise HTTPException(status_code=400, detail="方案与当前风格或部位不匹配")
            _upsert_line(
                db,
                selection,
                part_id=part_id,
                scheme_id=scheme.id,
                procurement_item_id=None,
                room_or_zone="",
                brand_tier=None,
                quantity=1,
            )
            changed = True
    if body.lines:
        for line in body.lines:
            _validate_line(db, selection, line)
            _upsert_line(
                db,
                selection,
                part_id=line.part_id,
                scheme_id=line.scheme_id,
                procurement_item_id=line.procurement_item_id,
                room_or_zone=line.room_or_zone,
                brand_tier=line.brand_tier,
                quantity=line.quantity,
                explicit_items=line.items,
                include_all=True,
            )
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
