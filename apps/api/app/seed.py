import json
import logging
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    Customer,
    CustomerSelection,
    Part,
    ProcurementItem,
    ProcurementTable,
    Project,
    Room,
    Scheme,
    SelectionLine,
    Style,
    UnitType,
)
from app.services.importer import parse_price_table

logger = logging.getLogger(__name__)
CATALOG_PATH = Path(__file__).resolve().parents[3] / "packages" / "catalog" / "catalog.json"
SAMPLE_CSV = Path(__file__).resolve().parents[3] / "packages" / "catalog" / "sample_sanitary.csv"
SAMPLE_TABLE_ID = "price_sanitary_sample"


def load_catalog() -> dict:
    with CATALOG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle, parse_float=lambda value: float(value))


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _upsert_project(db: Session, payload: dict) -> Project:
    project = db.get(Project, payload["id"])
    fields = {
        "code": payload["code"],
        "name": payload["name"],
        "developer": payload["developer"],
        "city": payload["city"],
        "district": payload["district"],
        "address": payload["address"],
        "description": payload["description"],
        "hard_cost_per_m2": payload["hard_cost_per_m2"],
        "soft_cost_per_m2": payload["soft_cost_per_m2"],
    }
    if project is None:
        project = Project(id=payload["id"], status=payload["status"], **fields)
        db.add(project)
    else:
        for key, value in fields.items():
            setattr(project, key, value)
    db.flush()
    return project


def _upsert_unit(db: Session, project: Project, payload: dict) -> UnitType:
    unit_id = f"{project.id}-{payload['code'].lower()}"
    unit = db.get(UnitType, unit_id)
    fields = {
        "code": payload["code"],
        "name": payload["name"],
        "building_area_m2": payload["building_area_m2"],
        "finish_area_override": None,
        "bedrooms": payload["bedrooms"],
        "living_rooms": payload["living_rooms"],
        "kitchens": payload["kitchens"],
        "bathrooms": payload["bathrooms"],
        "summary": payload["summary"],
    }
    if unit is None:
        unit = UnitType(id=unit_id, project_id=project.id, **fields)
        db.add(unit)
        db.flush()
    else:
        for key, value in fields.items():
            setattr(unit, key, value)
    db.execute(delete(Room).where(Room.unit_type_id == unit.id))
    for index, room in enumerate(payload["rooms"]):
        db.add(
            Room(
                id=f"{unit.id}-r{index + 1}",
                unit_type_id=unit.id,
                name=room["name"],
                area_m2=room["area_m2"],
                counts_toward_finish=bool(room["counts_toward_finish"]),
                sort_order=index,
            )
        )
    db.flush()
    return unit


def _ensure_drawing(db: Session, project: Project, units: dict[str, UnitType], payload: dict) -> None:
    if db.get(Asset, payload["id"]) is not None:
        return
    unit = units[payload["unit_code"]]
    db.add(
        Asset(
            id=payload["id"],
            project_id=project.id,
            unit_type_id=unit.id,
            kind=payload["kind"],
            filename=payload["filename"],
            content_type=payload["content_type"],
            byte_size=0,
            storage_key=None,
            status="placeholder",
            note=payload["note"],
        )
    )


def _upsert_catalog_prices(db: Session, catalog: dict) -> None:
    for part in catalog["parts"]:
        fields = {
            "name": part["name"],
            "sort_order": part["sort_order"],
            "pricing_mode": part.get("pricing", "area"),
            "allows_brand_tier": bool(part.get("allows_brand_tier", False)),
            "visual": bool(part.get("visual", False)),
        }
        row = db.get(Part, part["id"])
        if row is None:
            db.add(Part(id=part["id"], **fields))
        else:
            for key, value in fields.items():
                setattr(row, key, value)
    db.flush()
    for style_payload in catalog["styles"]:
        style = db.get(Style, style_payload["id"])
        fields = {
            "name": style_payload["name"],
            "tagline": style_payload["tagline"],
            "description": style_payload["description"],
            "palette": list(style_payload["palette"]),
            "sort_order": style_payload["sort_order"],
        }
        if style is None:
            db.add(Style(id=style_payload["id"], **fields))
        else:
            for key, value in fields.items():
                setattr(style, key, value)
    db.flush()
    for style_payload in catalog["styles"]:
        for part_id, schemes in style_payload["schemes"].items():
            indexes = [item["index"] for item in schemes]
            if indexes != [1, 2, 3]:
                raise RuntimeError(f"{style_payload['id']} / {part_id} 需要且仅需要方案 1、2、3")
            for item in schemes:
                scheme_id = f"{style_payload['id']}-{part_id}-{item['index']}"
                scheme = db.get(Scheme, scheme_id)
                scheme_fields = {
                    "style_id": style_payload["id"],
                    "part_id": part_id,
                    "scheme_index": item["index"],
                    "name": item["name"],
                    "summary": item["summary"],
                    "unit_price": item["unit_price"],
                    "is_default": item["index"] == 1,
                    "material": _json_safe(item["material"]),
                }
                if scheme is None:
                    db.add(Scheme(id=scheme_id, **scheme_fields))
                else:
                    for key, value in scheme_fields.items():
                        setattr(scheme, key, value)
    for item in catalog.get("sku_options", []):
        scheme_id = f"{item['part_id']}-{item['index']}"
        scheme = db.get(Scheme, scheme_id)
        scheme_fields = {
            "style_id": None,
            "part_id": item["part_id"],
            "scheme_index": item["index"],
            "name": item["name"],
            "summary": item["summary"],
            "unit_price": item["unit_price"],
            "is_default": item["index"] == 1,
            "material": {},
        }
        if scheme is None:
            db.add(Scheme(id=scheme_id, **scheme_fields))
        else:
            for key, value in scheme_fields.items():
                setattr(scheme, key, value)
    db.flush()


def _ensure_sample_prices(db: Session, project: Project) -> None:
    rows = parse_price_table(SAMPLE_CSV.name, SAMPLE_CSV.read_bytes(), "sanitary")
    table = db.get(ProcurementTable, SAMPLE_TABLE_ID)
    if table is None:
        table = ProcurementTable(
            id=SAMPLE_TABLE_ID,
            project_id=project.id,
            category="sanitary",
            title="洁具集采示例价表",
            original_filename=SAMPLE_CSV.name,
        )
        db.add(table)
        db.flush()
    else:
        table.project_id = project.id
        table.category = "sanitary"
        table.title = "洁具集采示例价表"
        table.original_filename = SAMPLE_CSV.name
        db.execute(delete(ProcurementItem).where(ProcurementItem.table_id == table.id))
    for index, row in enumerate(rows, start=1):
        db.add(ProcurementItem(id=f"{SAMPLE_TABLE_ID}_{index:03d}", table_id=table.id, **row))


def _ensure_demo(db: Session, catalog: dict, project: Project, units: dict[str, UnitType]) -> None:
    demo = catalog["demo"]
    customer = db.scalar(select(Customer).where(Customer.phone == demo["phone"]))
    if customer is None:
        customer = Customer(id="cus_demo", phone=demo["phone"], display_name=demo["display_name"])
        db.add(customer)
        db.flush()
    style_id = demo["style_id"]
    selection = db.get(CustomerSelection, demo["selection_id"])
    if selection is None:
        selection = CustomerSelection(
            id=demo["selection_id"],
            customer_id=customer.id,
            project_id=project.id,
            unit_type_id=units[demo["unit_code"]].id,
            style_id=style_id,
            ceiling_scheme_id=f"{style_id}-ceiling-1",
            floor_scheme_id=f"{style_id}-floor-1",
            wall_scheme_id=f"{style_id}-wall-1",
            status=demo.get("status", "draft"),
        )
        db.add(selection)
        db.flush()
    for part_id in ("ceiling", "floor", "wall"):
        scheme_id = f"{style_id}-{part_id}-1"
        line_id = f"{selection.id}-{part_id}"
        line = db.get(SelectionLine, line_id)
        if line is None:
            db.add(
                SelectionLine(
                    id=line_id,
                    selection_id=selection.id,
                    part_id=part_id,
                    room_or_zone="",
                    scheme_id=getattr(selection, f"{part_id}_scheme_id") or scheme_id,
                    quantity=1,
                )
            )


def seed(db: Session) -> None:
    catalog = load_catalog()
    project = _upsert_project(db, catalog["project"])
    units = {payload["code"]: _upsert_unit(db, project, payload) for payload in catalog["unit_types"]}
    for drawing in catalog["drawings"]:
        _ensure_drawing(db, project, units, drawing)
    _upsert_catalog_prices(db, catalog)
    _ensure_sample_prices(db, project)
    _ensure_demo(db, catalog, project, units)
    db.commit()
    logger.info("seed ready: project %s, styles %s", project.code, len(catalog["styles"]))
