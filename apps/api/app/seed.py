import json
import logging
from decimal import Decimal, ROUND_HALF_UP
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
    SchemeItem,
    SelectionLine,
    Style,
    UnitType,
)
from app.services.catalog_seed import seed_demo_bindings, seed_example_products
from app.services.internal_catalog import seed_internal_samples
from app.services.visual_demo import seed_visual_demo
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
    _seed_scheme_items(db)
    db.flush()


def _money(value: str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _slot(
    slug: str,
    name: str,
    room: str,
    group: str,
    price: str,
    quantity: int,
    display_part: str | None = None,
) -> dict:
    return {
        "slug": slug,
        "name": name,
        "room_name": room,
        "group_label": group,
        "unit_price": _money(price),
        "default_quantity": quantity,
        "display_part_id": display_part,
    }


def _slots_for(scheme: Scheme) -> list[dict]:
    """Room slots under a scheme. Lighting rides on the ceiling scheme."""
    index = scheme.scheme_index
    part_id = scheme.part_id
    if part_id == "ceiling":
        if index == 2:
            lights = [
                _slot("spot-living", "射灯／筒灯", "客厅", "客厅天花 · 12 个射灯／筒灯", "110", 12, "lighting"),
                _slot("spot-dining", "射灯", "餐厅", "餐厅天花 · 6 个射灯", "110", 6, "lighting"),
                _slot("spot-master", "筒灯", "主卧", "主卧天花 · 6 个筒灯", "100", 6, "lighting"),
            ]
        elif index == 3:
            lights = [
                _slot("spot-living", "射灯／筒灯", "客厅", "客厅天花 · 6 个射灯／筒灯", "140", 6, "lighting"),
                _slot("spot-dining", "射灯", "餐厅", "餐厅天花 · 4 个射灯", "140", 4, "lighting"),
                _slot("spot-master", "筒灯", "主卧", "主卧天花 · 2 个筒灯", "140", 2, "lighting"),
            ]
        else:
            lights = [
                _slot("spot-living", "射灯／筒灯", "客厅", "客厅天花 · 9 个射灯／筒灯", "90", 9, "lighting"),
                _slot("spot-dining", "射灯", "餐厅", "餐厅天花 · 5 个射灯", "90", 5, "lighting"),
                _slot("spot-master", "筒灯", "主卧", "主卧天花 · 4 个筒灯", "85", 4, "lighting"),
            ]
        return [_slot("cove", "灯槽灯带", "客厅", "客厅天花 · 灯槽", "160", 1), *lights]
    if part_id == "wall":
        return [
            _slot("panel", "背景墙板", "客厅", "客厅 · 背景墙板", "860", 1),
            _slot("trim", "造型线", "客厅", "客厅 · 造型线", "220", 1),
        ]
    if part_id == "floor":
        return [
            _slot("border", "波打线", "客厅", "客厅 · 波打线", "96", 1),
            _slot("sill", "过门石", "厨房", "厨房 · 过门石", "180", 1),
        ]
    if part_id == "cabinetry" and index == 1:
        return [
            _slot("tv", "电视柜", "客厅", "客厅 · 电视柜", "4200", 1),
            _slot("side", "餐边柜", "餐厅", "餐厅 · 餐边柜", "2600", 1),
        ]
    if part_id == "cabinetry":
        return [
            _slot("tv", "电视柜", "客厅", "客厅 · 电视柜", "2200", 1),
            _slot("side", "餐边柜", "餐厅", "餐厅 · 餐边柜", "1400", 1),
            _slot("wardrobe", "衣柜", "主卧", "主卧 · 衣柜", "4600", 1),
            _slot("book", "书柜", "主卧", "主卧 · 书柜", "1800", 1),
            _slot("night", "床头柜", "主卧", "主卧 · 床头柜", "900", 1),
            _slot("second", "衣柜", "次卧", "次卧 · 衣柜", "1900", 1),
        ]
    if part_id == "sanitary" and index == 1:
        return [
            _slot("shower", "花洒", "公卫", "公卫 · 花洒", "580", 1),
            _slot("basin", "面盆龙头", "公卫", "公卫 · 面盆龙头", "420", 1),
            _slot("wc", "马桶", "公卫", "公卫 · 马桶", "480", 1),
            _slot("tap", "龙头", "厨房", "厨房 · 龙头", "80", 1),
            _slot("sink", "菜盆", "厨房", "厨房 · 菜盆", "120", 1),
        ]
    if part_id == "sanitary":
        return [
            _slot("shower", "花洒", "公卫", "公卫 · 花洒", "720", 1),
            _slot("basin", "面盆龙头", "公卫", "公卫 · 面盆龙头", "560", 1),
            _slot("wc", "马桶", "公卫", "公卫 · 马桶", "640", 1),
            _slot("mshower", "花洒", "主卫", "主卫 · 花洒", "720", 1),
            _slot("mwc", "马桶", "主卫", "主卫 · 马桶", "360", 1),
            _slot("tap", "龙头", "厨房", "厨房 · 龙头", "80", 1),
            _slot("sink", "菜盆", "厨房", "厨房 · 菜盆", "120", 1),
        ]
    if part_id == "kitchen_appliance" and index == 1:
        return [
            _slot("hood", "烟机", "厨房", "厨房 · 烟机", "2490", 1),
            _slot("hob", "炉灶", "厨房", "厨房 · 炉灶", "1500", 1),
        ]
    if part_id == "kitchen_appliance":
        return [
            _slot("hood", "烟机", "厨房", "厨房 · 烟机", "3200", 1),
            _slot("hob", "炉灶", "厨房", "厨房 · 炉灶", "2100", 1),
            _slot("oven", "蒸烤箱", "厨房", "厨房 · 蒸烤箱", "2890", 1),
            _slot("washer", "洗碗机", "厨房", "厨房 · 洗碗机", "800", 1),
        ]
    if part_id == "switch_socket" and index == 1:
        return [
            _slot("living", "开关插座", "客厅", "客厅 · 开关插座", "15", 12),
            _slot("master", "开关插座", "主卧", "主卧 · 开关插座", "15", 8),
            _slot("kitchen", "开关插座", "厨房", "厨房 · 开关插座", "15", 6),
            _slot("bath", "开关插座", "公卫", "公卫 · 开关插座", "15", 6),
        ]
    if part_id == "switch_socket":
        return [
            _slot("living", "开关插座", "客厅", "客厅 · 开关插座", "20", 18),
            _slot("master", "开关插座", "主卧", "主卧 · 开关插座", "20", 12),
            _slot("second", "开关插座", "次卧", "次卧 · 开关插座", "20", 10),
            _slot("kitchen", "开关插座", "厨房", "厨房 · 开关插座", "20", 10),
            _slot("bath", "开关插座", "公卫", "公卫 · 开关插座", "20", 8),
            _slot("dining", "开关插座", "餐厅", "餐厅 · 开关插座", "20", 6),
        ]
    if part_id == "entry_door":
        price = Decimal(str(scheme.unit_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return [
            {
                "slug": "leaf",
                "name": "门扇",
                "room_name": "",
                "group_label": "整户 · 1 樘入户门",
                "unit_price": price,
                "default_quantity": 1,
                "display_part_id": None,
            }
        ]
    return []


def _seed_scheme_items(db: Session) -> None:
    schemes = db.scalars(select(Scheme)).all()
    for scheme in schemes:
        wanted = _slots_for(scheme)
        keep = set()
        for sort_order, slot in enumerate(wanted):
            item_id = f"{scheme.id}-{slot['slug']}"
            keep.add(item_id)
            row = db.get(SchemeItem, item_id)
            fields = {
                "scheme_id": scheme.id,
                "name": slot["name"],
                "room_name": slot["room_name"],
                "group_label": slot["group_label"],
                "display_part_id": slot["display_part_id"],
                "unit_price": slot["unit_price"],
                "default_quantity": slot["default_quantity"],
                "sort_order": sort_order,
            }
            if row is None:
                db.add(SchemeItem(id=item_id, **fields))
            else:
                for key, value in fields.items():
                    setattr(row, key, value)
        for stale in list(scheme.items or []):
            if stale.id not in keep:
                db.delete(stale)


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
    seed_example_products(db)
    if "A" in units:
        seed_demo_bindings(db, project.id, units["A"].id)
        demo = catalog.get("demo") or {}
        if demo.get("selection_id"):
            seed_visual_demo(db, project.id, units["A"].id, demo["selection_id"])
    seed_internal_samples(db)
    db.commit()
    logger.info("seed ready: project %s, styles %s", project.code, len(catalog["styles"]))
