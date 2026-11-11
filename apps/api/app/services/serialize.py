from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.constants import CATEGORY_LABELS, KIND_LABELS
from app.models import Asset, Part, Project, ProjectBinding, Scheme, SelectionLine, Style, UnitType
from app.services.placement import active_plan, plan_dict, substitutes_for
from app.services.quote import (
    PricedPart,
    QuoteResult,
    RoomArea,
    as_decimal,
    compute_quote,
    resolve_area,
)


def num(value) -> float:
    return float(Decimal(str(value)))


def iso(value) -> str:
    if value is None:
        return ""
    return value.isoformat()


def scheme_dict(scheme: Scheme) -> dict:
    material = scheme.material or {}
    return {
        "id": scheme.id,
        "style_id": scheme.style_id,
        "part_id": scheme.part_id,
        "index": scheme.scheme_index,
        "name": scheme.name,
        "summary": scheme.summary,
        "unit_price": num(scheme.unit_price),
        "is_default": bool(scheme.is_default),
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "room_name": item.room_name or "",
                "group_label": item.group_label or item.name,
                "display_part_id": item.display_part_id,
                "unit_price": num(item.unit_price),
                "default_quantity": num(item.default_quantity),
                "sort_order": item.sort_order,
            }
            for item in sorted(scheme.items or [], key=lambda row: row.sort_order)
        ],
        "material": {
            "color": material.get("color", "#dddddd"),
            "roughness": float(material.get("roughness", 0.8)),
            "metalness": float(material.get("metalness", 0)),
            "accent": material.get("accent", "#cccccc"),
            "feature": material.get("feature", "paint"),
        },
    }


def style_dict(db: Session, style: Style) -> dict:
    parts = db.scalars(select(Part).order_by(Part.sort_order, Part.id)).all()
    schemes = db.scalars(select(Scheme).where(Scheme.style_id == style.id)).all()
    grouped = []
    for part in parts:
        items = sorted((item for item in schemes if item.part_id == part.id), key=lambda item: item.scheme_index)
        if not items:
            continue
        grouped.append({"id": part.id, "name": part.name, "schemes": [scheme_dict(item) for item in items]})
    return {
        "id": style.id,
        "name": style.name,
        "tagline": style.tagline,
        "description": style.description,
        "palette": list(style.palette or []),
        "parts": grouped,
    }


def asset_dict(asset: Asset) -> dict:
    return {
        "id": asset.id,
        "project_id": asset.project_id,
        "unit_type_id": asset.unit_type_id,
        "selection_id": asset.selection_id,
        "kind": asset.kind,
        "kind_label": KIND_LABELS.get(asset.kind, asset.kind),
        "filename": asset.filename,
        "content_type": asset.content_type,
        "byte_size": asset.byte_size,
        "status": asset.status,
        "note": asset.note or "",
        "created_at": iso(asset.created_at),
    }


def room_dict(room) -> dict:
    return {
        "id": room.id,
        "name": room.name,
        "area_m2": num(room.area_m2),
        "counts_toward_finish": bool(room.counts_toward_finish),
    }


def unit_area(unit: UnitType):
    rooms = [
        RoomArea(room.name, as_decimal(room.area_m2), bool(room.counts_toward_finish))
        for room in unit.rooms
    ]
    override = None if unit.finish_area_override is None else as_decimal(unit.finish_area_override)
    return resolve_area(rooms, as_decimal(unit.building_area_m2), override)


def unit_dict(db: Session, unit: UnitType, selection_id: str | None = None) -> dict:
    area, basis, excluded, note = unit_area(unit)
    filters = [Asset.unit_type_id == unit.id]
    if selection_id:
        filters.append(Asset.selection_id == selection_id)
    assets = db.scalars(select(Asset).where(or_(*filters)).order_by(Asset.created_at)).all()
    seen = set()
    unique_assets = []
    for asset in assets:
        if asset.id in seen:
            continue
        seen.add(asset.id)
        unique_assets.append(asset)
    return {
        "id": unit.id,
        "project_id": unit.project_id,
        "code": unit.code,
        "name": unit.name,
        "building_area_m2": num(unit.building_area_m2),
        "finish_area_m2": num(area),
        "area_basis": basis,
        "area_note": note,
        "bedrooms": unit.bedrooms,
        "living_rooms": unit.living_rooms,
        "kitchens": unit.kitchens,
        "bathrooms": unit.bathrooms,
        "summary": unit.summary,
        "excluded_rooms": excluded,
        "rooms": [room_dict(room) for room in unit.rooms],
        "assets": [asset_dict(asset) for asset in unique_assets],
    }


def project_brief(project: Project) -> dict:
    return {
        "id": project.id,
        "code": project.code,
        "name": project.name,
        "developer": project.developer,
        "city": project.city,
        "district": project.district,
        "address": project.address,
        "status": project.status,
        "hard_cost_per_m2": num(project.hard_cost_per_m2),
        "soft_cost_per_m2": num(project.soft_cost_per_m2),
    }


def project_dict(db: Session, project: Project) -> dict:
    data = project_brief(project)
    data["description"] = project.description
    units = db.scalars(
        select(UnitType).where(UnitType.project_id == project.id).order_by(UnitType.code)
    ).all()
    data["unit_types"] = [unit_dict(db, unit) for unit in units]
    return data


def _line_price(line: SelectionLine):
    if line.scheme is not None:
        return as_decimal(line.scheme.unit_price), line.scheme.id, line.scheme.name
    if line.procurement_item is not None:
        return as_decimal(line.procurement_item.unit_price), None, line.procurement_item.name
    return None, None, None


def quote_for_selection(db: Session, selection) -> QuoteResult:
    unit = selection.unit
    rooms = [
        RoomArea(room.name, as_decimal(room.area_m2), bool(room.counts_toward_finish))
        for room in unit.rooms
    ]
    part_rows = {part.id: part for part in db.scalars(select(Part)).all()}
    parts: list[PricedPart] = []
    if selection.style_id:
        named = {
            "ceiling": selection.ceiling_scheme,
            "floor": selection.floor_scheme,
            "wall": selection.wall_scheme,
        }
        for part_id in ("ceiling", "floor", "wall"):
            scheme = named[part_id]
            part = part_rows.get(part_id)
            parts.append(
                PricedPart(
                    part_id=part_id,
                    part_name=part.name if part else part_id,
                    scheme_id=scheme.id if scheme else None,
                    scheme_name=scheme.name if scheme else None,
                    unit_price=None if scheme is None else as_decimal(scheme.unit_price),
                    pricing="area",
                )
            )
    for line in selection.lines or []:
        part = part_rows.get(line.part_id)
        if part is None:
            continue
        included = [pick for pick in (line.picks or []) if pick.included and pick.item is not None]
        if included:
            for pick in included:
                display_id = pick.item.display_part_id or line.part_id
                display = part_rows.get(display_id)
                title = display.name if display else part.name
                room = (pick.item.room_name or "").strip()
                label = f"{title}·{room}·{pick.item.name}" if room else f"{title}·{pick.item.name}"
                unit_price = as_decimal(pick.item.unit_price)
                if pick.product is not None and pick.product.status == "confirmed":
                    chosen = pick.product.import_price if (pick.brand_tier or line.brand_tier) == "import" else pick.product.domestic_price
                    unit_price = as_decimal(chosen)
                    label = f"{label}·{pick.product.model_code}"
                parts.append(
                    PricedPart(
                        part_id=f"{display_id}#{pick.scheme_item_id}",
                        part_name=label,
                        scheme_id=line.scheme_id,
                        scheme_name=pick.item.group_label or pick.item.name,
                        unit_price=unit_price,
                        pricing="each",
                        quantity=as_decimal(pick.quantity or 1),
                        brand_tier=pick.brand_tier or line.brand_tier,
                    )
                )
            continue
        if part.pricing_mode == "area" or line.picks:
            continue
        unit_price, scheme_id, scheme_name = _line_price(line)
        if unit_price is None:
            continue
        parts.append(
            PricedPart(
                part_id=line.part_id,
                part_name=part.name,
                scheme_id=scheme_id or line.scheme_id,
                scheme_name=scheme_name,
                unit_price=unit_price,
                pricing="each",
                quantity=as_decimal(line.quantity or 1),
                brand_tier=line.brand_tier,
            )
        )
    return compute_quote(
        rooms=rooms,
        building_area=as_decimal(unit.building_area_m2),
        finish_override=None if unit.finish_area_override is None else as_decimal(unit.finish_area_override),
        parts=parts,
        hard_cost_per_m2=as_decimal(selection.project.hard_cost_per_m2),
        soft_cost_per_m2=as_decimal(selection.project.soft_cost_per_m2),
    )


def quote_dict(result: QuoteResult) -> dict:
    return {
        "finish_area_m2": num(result.finish_area_m2),
        "area_basis": result.area_basis,
        "area_note": result.area_note,
        "excluded_rooms": result.excluded_rooms,
        "lines": [
            {
                "part_id": line.part_id,
                "part_name": line.part_name,
                "scheme_id": line.scheme_id,
                "scheme_name": line.scheme_name,
                "unit_price": None if line.unit_price is None else num(line.unit_price),
                "area_m2": num(line.area_m2),
                "amount": num(line.amount),
                "pricing": line.pricing,
                "quantity": num(line.quantity),
                "brand_tier": line.brand_tier,
            }
            for line in result.lines
        ],
        "total": num(result.total),
        "reference": {key: num(value) if key != "note" else value for key, value in result.reference.items()},
    }


def part_catalog(db: Session, style_id: str | None) -> list[dict]:
    parts = db.scalars(select(Part).order_by(Part.sort_order, Part.id)).all()
    rows = []
    for part in parts:
        if part.visual:
            query = select(Scheme).where(Scheme.part_id == part.id, Scheme.style_id == style_id)
            schemes = [] if style_id is None else db.scalars(query).all()
        else:
            schemes = db.scalars(select(Scheme).where(Scheme.part_id == part.id, Scheme.style_id.is_(None))).all()
        rows.append(
            {
                "id": part.id,
                "name": part.name,
                "sort_order": part.sort_order,
                "pricing": part.pricing_mode,
                "visual": bool(part.visual),
                "allows_brand_tier": bool(part.allows_brand_tier),
                "schemes": [scheme_dict(item) for item in sorted(schemes, key=lambda item: item.scheme_index)],
            }
        )
    return rows


def line_dict(line: SelectionLine) -> dict:
    return {
        "id": line.id,
        "part_id": line.part_id,
        "part_name": line.part.name if line.part is not None else line.part_id,
        "room_or_zone": line.room_or_zone or "",
        "scheme_id": line.scheme_id,
        "scheme_name": None if line.scheme is None else line.scheme.name,
        "procurement_item_id": line.procurement_item_id,
        "brand_tier": line.brand_tier,
        "quantity": num(line.quantity or 1),
        "picks": [
            {
                "id": pick.id,
                "scheme_item_id": pick.scheme_item_id,
                "name": pick.item.name if pick.item is not None else "",
                "room_name": "" if pick.item is None else (pick.item.room_name or ""),
                "group_label": "" if pick.item is None else (pick.item.group_label or pick.item.name),
                "display_part_id": line.part_id if pick.item is None or not pick.item.display_part_id else pick.item.display_part_id,
                "unit_price": num(pick.item.unit_price) if pick.item is not None else 0,
                "included": bool(pick.included),
                "quantity": num(pick.quantity or 1),
                "brand_tier": pick.brand_tier,
                "product_id": pick.product_id,
                "product_name": None if pick.product is None else pick.product.name,
                "width_mm": None if pick.product is None else pick.product.width_mm,
                "depth_mm": None if pick.product is None else pick.product.depth_mm,
                "height_mm": None if pick.product is None else pick.product.height_mm,
            }
            for pick in line.picks or []
        ],
    }


def selection_dict(db: Session, selection) -> dict:
    quote = quote_dict(quote_for_selection(db, selection))
    return {
        "id": selection.id,
        "status": selection.status,
        "customer_phone": selection.customer.phone,
        "customer_name": selection.customer.display_name,
        "project": project_brief(selection.project),
        "unit": unit_dict(db, selection.unit, selection.id),
        "style": None if selection.style is None else style_dict(db, selection.style),
        "ceiling": None if selection.ceiling_scheme is None else scheme_dict(selection.ceiling_scheme),
        "floor": None if selection.floor_scheme is None else scheme_dict(selection.floor_scheme),
        "wall": None if selection.wall_scheme is None else scheme_dict(selection.wall_scheme),
        "parts": part_catalog(db, selection.style_id),
        "lines": [line_dict(line) for line in sorted(selection.lines or [], key=lambda item: item.part_id)],
        "bindings": [
            {
                "id": row.id,
                "room_name": row.room_name or "",
                "part_id": row.part_id,
                "unit_type_id": row.unit_type_id,
                "product_id": row.product_id,
                "product_name": row.product.name if row.product is not None else "",
                "image_url": f"/api/products/{row.product_id}/image.svg",
            }
            for row in db.scalars(select(ProjectBinding).where(ProjectBinding.project_id == selection.project_id)).all()
        ],
        "quote": quote,
        "substitutes": substitutes_for(db, selection.id),
        "plan": _plan_for_selection(db, selection),
        "created_at": iso(selection.created_at),
        "updated_at": iso(selection.updated_at),
    }


def _plan_for_selection(db: Session, selection) -> dict | None:
    plan = active_plan(db, selection.project_id, selection.unit_type_id)
    if plan is None:
        return None
    return plan_dict(db, plan)


def selection_list_item(db: Session, selection) -> dict:
    total = quote_for_selection(db, selection).total
    return {
        "id": selection.id,
        "status": selection.status,
        "customer_phone": selection.customer.phone,
        "customer_name": selection.customer.display_name,
        "project_id": selection.project_id,
        "project_code": selection.project.code,
        "project_name": selection.project.name,
        "unit_id": selection.unit_type_id,
        "unit_name": selection.unit.name,
        "style_id": selection.style_id,
        "style_name": None if selection.style is None else selection.style.name,
        "total": num(total),
        "updated_at": iso(selection.updated_at),
    }


def price_item_dict(item) -> dict:
    return {
        "id": item.id,
        "category": item.category,
        "category_label": CATEGORY_LABELS.get(item.category, item.category),
        "sku_code": item.sku_code,
        "name": item.name,
        "spec": item.spec,
        "brand": item.brand,
        "unit": item.unit,
        "unit_price": num(item.unit_price),
        "remark": item.remark,
    }


def price_table_dict(table, row_count: int, items=None) -> dict:
    data = {
        "id": table.id,
        "project_id": table.project_id,
        "category": table.category,
        "category_label": CATEGORY_LABELS.get(table.category, table.category),
        "title": table.title,
        "original_filename": table.original_filename,
        "row_count": row_count,
        "created_at": iso(table.created_at),
    }
    if items is not None:
        data["items"] = [price_item_dict(item) for item in items]
    return data
