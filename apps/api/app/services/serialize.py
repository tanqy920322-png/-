from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.constants import CATEGORY_LABELS, KIND_LABELS
from app.models import Asset, Part, Project, Scheme, Style, UnitType
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


def quote_for_selection(db: Session, selection) -> QuoteResult:
    unit = selection.unit
    rooms = [
        RoomArea(room.name, as_decimal(room.area_m2), bool(room.counts_toward_finish))
        for room in unit.rooms
    ]
    parts: list[PricedPart] = []
    if selection.style_id:
        named = {
            "ceiling": selection.ceiling_scheme,
            "floor": selection.floor_scheme,
            "wall": selection.wall_scheme,
        }
        part_rows = {part.id: part for part in db.scalars(select(Part)).all()}
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
            }
            for line in result.lines
        ],
        "total": num(result.total),
        "reference": {key: num(value) if key != "note" else value for key, value in result.reference.items()},
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
        "quote": quote,
        "created_at": iso(selection.created_at),
        "updated_at": iso(selection.updated_at),
    }


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
