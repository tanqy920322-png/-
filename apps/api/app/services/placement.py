"""Turn hand marks into the products and materials already chosen for the unit."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, CatalogProduct, PlanMark, PlanSheet, ProjectBinding, VisualSubstitute
from app.services.image_to_3d import PART_NAMES, default_size_mm, stand_in_notice
from app.services.sizes import DEFAULT_SIZES

SURFACE = {"ceiling", "wall", "floor"}
MARK_PARTS = SURFACE | {
    "sanitary",
    "sofa",
    "switch_socket",
    "cabinetry",
    "lighting",
    "entry_door",
    "kitchen_appliance",
}
PLAN_HONESTY = "这些点是人工点上的，系统按点摆放。不是自动识别施工图，也没有按 CAD 对齐。"


def _binding_index(db: Session, project_id: str, unit_type_id: str) -> dict[tuple[str, str], ProjectBinding]:
    rows = db.scalars(select(ProjectBinding).where(ProjectBinding.project_id == project_id)).all()
    index: dict[tuple[str, str], ProjectBinding] = {}
    for row in rows:
        if row.unit_type_id and row.unit_type_id != unit_type_id:
            continue
        index[(row.room_name or "", row.part_id)] = row
    return index


def mark_dict(mark: PlanMark, binding: ProjectBinding | None) -> dict:
    product: CatalogProduct | None = None if binding is None else binding.product
    if mark.part_id in SURFACE:
        role = "material"
    elif product is not None:
        role = "product"
    else:
        role = "empty"
    if product is not None and product.width_mm and product.depth_mm and product.height_mm:
        width, depth, height = product.width_mm, product.depth_mm, product.height_mm
    elif mark.part_id in DEFAULT_SIZES or mark.part_id == "sofa":
        width, depth, height = default_size_mm(mark.part_id, mark.slot_label or "")
    else:
        width, depth, height = (600, 600, 600)
    if product is None and role == "material":
        product_name = PART_NAMES.get(mark.part_id, mark.slot_label or mark.part_id)
    elif product is None:
        product_name = ""
    else:
        product_name = product.name
    return {
        "id": mark.id,
        "room_name": mark.room_name,
        "part_id": mark.part_id,
        "slot_label": mark.slot_label or PART_NAMES.get(mark.part_id, mark.part_id),
        "x": round(float(mark.x), 4),
        "y": round(float(mark.y), 4),
        "product_name": product_name,
        "width_mm": int(width),
        "depth_mm": int(depth),
        "height_mm": int(height),
        "role": role,
    }


def plan_dict(db: Session, plan: PlanSheet, *, preview_path: str | None = None) -> dict:
    bindings = _binding_index(db, plan.project_id, plan.unit_type_id)
    marks = sorted(plan.marks or [], key=lambda item: (item.room_name, item.slot_label, item.id))
    payload = {
        "id": plan.id,
        "project_id": plan.project_id,
        "unit_type_id": plan.unit_type_id,
        "filename": plan.filename,
        "media": plan.media,
        "note": plan.note or "",
        "active": bool(plan.active),
        "vectors": plan.vectors or [],
        "scale_m_per_unit": None if plan.scale_m_per_unit is None else float(plan.scale_m_per_unit),
        "wall_height_m": None if plan.wall_height_m is None else float(plan.wall_height_m),
        "marks": [mark_dict(mark, bindings.get((mark.room_name, mark.part_id))) for mark in marks],
        "honesty": PLAN_HONESTY,
    }
    if preview_path:
        payload["preview_path"] = preview_path
    return payload


def active_plan(db: Session, project_id: str, unit_type_id: str) -> PlanSheet | None:
    rows = db.scalars(
        select(PlanSheet)
        .where(PlanSheet.project_id == project_id, PlanSheet.unit_type_id == unit_type_id)
        .order_by(PlanSheet.created_at.desc())
    ).all()
    if not rows:
        return None
    for row in rows:
        if row.active:
            return row
    return rows[0]


def substitute_dict(row: VisualSubstitute, selection_id: str) -> dict:
    notice = stand_in_notice(photo_count=2 if row.secondary_asset_id else 1, demo=bool(row.demo))
    payload = {
        "id": row.id,
        "part_id": row.part_id,
        "part_name": PART_NAMES.get(row.part_id, row.part_id),
        "room_name": row.room_name,
        "slot_label": row.slot_label,
        "width_mm": row.width_mm,
        "depth_mm": row.depth_mm,
        "height_mm": row.height_mm,
        "photo_path": f"/api/selections/{selection_id}/substitutes/{row.id}/photo",
        "extra_photo_path": None
        if row.secondary_asset_id is None
        else f"/api/selections/{selection_id}/substitutes/{row.id}/photo?index=2",
        "demo": bool(row.demo),
        **notice,
    }
    return payload


def substitutes_for(db: Session, selection_id: str) -> list[dict]:
    rows = db.scalars(
        select(VisualSubstitute)
        .where(VisualSubstitute.selection_id == selection_id)
        .order_by(VisualSubstitute.created_at, VisualSubstitute.id)
    ).all()
    return [substitute_dict(row, selection_id) for row in rows]


def remove_asset(db: Session, asset_id: str | None) -> None:
    if not asset_id:
        return
    asset = db.get(Asset, asset_id)
    if asset is None:
        return
    if asset.storage_key:
        from app.services.storage import get_storage

        get_storage().delete(asset.storage_key)
    db.delete(asset)
