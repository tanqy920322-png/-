"""Print-time bill of quantities. Separate from the selection quote.

Quantities come from ``takeoff_geometry`` and from pieces the customer already
chose. The fixed rule table decides which lines a scheme breaks into.
``UnconnectedModelMapper`` is consulted only to record that it is not connected.
It never supplies a length, an area, or a price.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import CATEGORY_LABELS
from app.models import Asset, GeneratedCandidate
from app.services.placement import active_plan, substitutes_for
from app.services.quote import money
from app.services.serialize import quote_dict, quote_for_selection
from app.services.storage import get_storage
from app.services.takeoff_geometry import (
    NOT_ON_PLAN,
    NO_VECTOR,
    POINT_ONLY,
    UNMARKED,
    UNNAMED,
    DrawnRoom,
    Measure,
    area_above_band,
    band_area,
    open_run,
    room_area,
    room_perimeter,
    rooms_from_dxf,
    rooms_from_svg,
    wall_area,
)
from app.services.takeoff_mapping import (
    EXCLUSION_ITEMS,
    GEOMETRY_NOTE,
    INSTITUTION,
    MAPPING_HONESTY,
    SELECTION_NOTE,
    BreakdownLine,
    FixedRuleMapper,
    UnconnectedModelMapper,
)

PART_ORDER = (
    "ceiling",
    "wall",
    "floor",
    "cabinetry",
    "sanitary",
    "entry_door",
    "kitchen_appliance",
    "lighting",
    "switch_socket",
)
ALWAYS_SECTIONS = ("ceiling", "wall", "floor")
INSTALL_PARTS = (
    "cabinetry",
    "sanitary",
    "entry_door",
    "kitchen_appliance",
    "lighting",
    "switch_socket",
)
PIECE_UNIT = {
    "entry_door": "樘",
    "lighting": "个",
    "switch_socket": "个",
    "kitchen_appliance": "台",
    "sanitary": "件",
    "cabinetry": "件",
    "ceiling": "项",
    "wall": "项",
    "floor": "项",
}
AREA_REMARK = "按闭合墙线鞋带面积乘以比例的平方。墙厚未标，不扣。"
EDGE_REMARK = "边长已按闭合墙线算出。方案单价是按平方米，没有每米单价，这条不计入算量小计。"
WALL_REMARK = "按闭合墙线周长乘标明层高。门窗洞未标，不扣洞口，也不估洞口尺寸。"
BAND_REMARK = "这段高度写在方案的固定规则里，再乘闭合周长。不是估的层高。"
SPLIT_REMARK = "方案是一个平方米单价，没有拆成两道单价，这条只报数量，不计入算量小计。"
INSTALL_REMARK = "安装工费未计算，不计入算量小计。"
UNCONFIRMED_REMARK = "未确认或未完成生成，不进入计价行，也不能下单。"
EFFECT_REMARK = "仅用于效果展示，不列入采购，不能下单。"


def _num(value: Decimal | None):
    if value is None:
        return None
    return float(value)


def _join(reasons: list[str]) -> str:
    seen: list[str] = []
    for reason in reasons:
        if reason and reason not in seen:
            seen.append(reason)
    return "；".join(seen)


@dataclass
class RoomLoop:
    name: str
    polygon: list[tuple[float, float]] | None
    on_plan: bool


@dataclass
class SchemeIn:
    part_id: str
    part_name: str
    scheme_name: str
    feature: str
    unit_price: Decimal | None
    pricing: str = "area"


@dataclass
class PickIn:
    part_id: str
    room_name: str
    name: str
    quantity: Decimal
    unit_price: Decimal
    included: bool
    product_status: str | None = None
    craft: str = ""


@dataclass
class RunIn:
    room_name: str
    part_id: str
    points: list[tuple[float, float]]


@dataclass
class TakeoffInput:
    selection_id: str = ""
    customer_name: str = ""
    customer_phone: str = ""
    project_name: str = ""
    project_code: str = ""
    unit_name: str = ""
    style_name: str = ""
    selection_quote: dict = field(default_factory=dict)
    scale_m_per_unit: Decimal | None = None
    wall_height_m: Decimal | None = None
    plan_id: str = ""
    plan_filename: str = ""
    drawing_missing: bool = False
    rooms: list[RoomLoop] = field(default_factory=list)
    marks: set[tuple[str, str]] = field(default_factory=set)
    schemes: list[SchemeIn] = field(default_factory=list)
    picks: list[PickIn] = field(default_factory=list)
    runs: list[RunIn] = field(default_factory=list)
    substitutes: list[dict] = field(default_factory=list)
    generated: list[dict] = field(default_factory=list)


def _measure_for(kind: str, room: RoomLoop, scale, height, stated) -> Measure:
    polygon = room.polygon
    if kind == "area":
        return room_area(polygon, scale)
    if kind == "perimeter":
        return room_perimeter(polygon, scale)
    if kind == "wall_area":
        return wall_area(polygon, scale, height)
    if kind == "stated_band":
        return band_area(polygon, scale, stated)
    if kind == "above_band":
        return area_above_band(polygon, scale, height, stated)
    return Measure(None, ("这项没有固定的量法，数量留空",))


def _blockers(room: RoomLoop, part_id: str, marks: set[tuple[str, str]], drawing_missing: bool) -> list[str]:
    reasons: list[str] = []
    if not room.on_plan or not room.polygon:
        reasons.append(NO_VECTOR if drawing_missing else NOT_ON_PLAN)
        return reasons
    if not room.name:
        reasons.append(UNNAMED)
    elif (room.name, part_id) not in marks:
        reasons.append(UNMARKED)
    return reasons


def _line(
    *,
    room_name: str,
    item: str,
    unit: str,
    quantity: Decimal | None,
    craft: str,
    unit_price: Decimal | None,
    amount: Decimal | None,
    remark: str,
    included: bool,
) -> dict:
    priced = included and amount is not None
    return {
        "room_name": room_name,
        "item": item,
        "unit": unit,
        "quantity": _num(quantity),
        "craft": craft,
        "unit_price": _num(unit_price),
        "amount": _num(amount),
        "remark": remark,
        "included_in_subtotal": priced,
        "priced": priced,
    }


def _geometry_lines(data: TakeoffInput, scheme: SchemeIn, rules: tuple[BreakdownLine, ...]) -> list[dict]:
    rows: list[dict] = []
    priced_rooms: set[str] = set()
    for rule in rules:
        for index, room in enumerate(data.rooms):
            blockers = _blockers(room, scheme.part_id, data.marks, data.drawing_missing)
            measure = Measure(None, ())
            if room.on_plan and room.polygon:
                measure = _measure_for(
                    rule.kind,
                    room,
                    data.scale_m_per_unit,
                    data.wall_height_m,
                    rule.stated_height_m,
                )
            reasons = blockers + [reason for reason in measure.reasons if reason not in blockers]
            quantity = None if reasons else measure.quantity
            unit_price = None
            amount = None
            included = False
            room_key = room.name or f"#{index}"
            if quantity is not None and rule.unit == "m²" and room_key not in priced_rooms and scheme.unit_price is not None:
                unit_price = money(scheme.unit_price)
                amount = money(unit_price * quantity)
                included = True
                priced_rooms.add(room_key)
                remark = _join([AREA_REMARK if rule.kind == "area" else WALL_REMARK if rule.kind == "wall_area" else BAND_REMARK])
            elif quantity is not None and rule.unit == "m²":
                remark = SPLIT_REMARK
            elif quantity is not None and rule.unit == "m":
                remark = EDGE_REMARK
            else:
                remark = _join(reasons)
            label = f"{room.name} {rule.item}".strip()
            rows.append(
                _line(
                    room_name=room.name,
                    item=label,
                    unit=rule.unit,
                    quantity=quantity,
                    craft=scheme.scheme_name,
                    unit_price=unit_price,
                    amount=amount,
                    remark=remark,
                    included=included,
                )
            )
    return rows


def _run_lines(data: TakeoffInput, scheme: SchemeIn) -> list[dict]:
    marked = [room for room in data.rooms if room.name and (room.name, scheme.part_id) in data.marks]
    rows: list[dict] = []
    targets = marked or [RoomLoop(name="", polygon=None, on_plan=False)]
    for room in targets:
        run = next((item for item in data.runs if item.part_id == scheme.part_id and item.room_name == room.name), None)
        if run is None:
            remark = POINT_ONLY if room.name else UNMARKED
            quantity = None
        else:
            measured = open_run(run.points, data.scale_m_per_unit)
            quantity = measured.quantity
            remark = _join(list(measured.reasons)) or "延米按图上的线段乘比例。一个点不算长度。"
        label = f"{room.name} 柜体延米".strip()
        rows.append(
            _line(
                room_name=room.name,
                item=label,
                unit="m",
                quantity=quantity,
                craft=scheme.scheme_name,
                unit_price=None,
                amount=None,
                remark=remark,
                included=False,
            )
        )
    return rows


def _piece_lines(data: TakeoffInput, part_id: str) -> tuple[list[dict], list[dict]]:
    priced: list[dict] = []
    blocked: list[dict] = []
    for pick in data.picks:
        if not pick.included or pick.part_id != part_id:
            continue
        label = f"{pick.room_name} {pick.name}".strip()
        if pick.product_status not in (None, "", "confirmed"):
            blocked.append(
                {
                    "item": label,
                    "remark": UNCONFIRMED_REMARK,
                    "priced": False,
                    "included_in_subtotal": False,
                }
            )
            continue
        quantity = money(pick.quantity)
        unit_price = money(pick.unit_price)
        amount = money(unit_price * quantity)
        priced.append(
            _line(
                room_name=pick.room_name,
                item=label,
                unit=PIECE_UNIT.get(part_id, "件"),
                quantity=quantity,
                craft=pick.craft,
                unit_price=unit_price,
                amount=amount,
                remark="数量用客户已经勾选的件数，不另估。",
                included=True,
            )
        )
    return priced, blocked


def _section_subtotal(lines: list[dict]) -> float:
    total = Decimal("0")
    for line in lines:
        if line.get("included_in_subtotal") and line.get("amount") is not None:
            total += Decimal(str(line["amount"]))
    return float(money(total))


def _empty_part(part_id: str, title: str) -> dict:
    return {
        "id": part_id,
        "title": title,
        "lines": [
            _line(
                room_name="",
                item=title,
                unit="",
                quantity=None,
                craft="",
                unit_price=None,
                amount=None,
                remark="未选方案，不出计价行。",
                included=False,
            )
        ],
    }


def build_takeoff(data: TakeoffInput) -> dict:
    hook = UnconnectedModelMapper().map_scheme("", "", "")
    mapper = FixedRuleMapper()
    schemes = {item.part_id: item for item in data.schemes}
    picked_parts = {pick.part_id for pick in data.picks if pick.included}
    unpriced: list[dict] = []
    sections: list[dict] = []

    for part_id in PART_ORDER:
        title = CATEGORY_LABELS.get(part_id, part_id)
        scheme = schemes.get(part_id)
        show = part_id in ALWAYS_SECTIONS or scheme is not None or part_id in picked_parts
        if not show:
            continue
        if scheme is None and part_id not in picked_parts:
            sections.append(_empty_part(part_id, title))
            continue
        lines: list[dict] = []
        if scheme is not None and part_id in ("ceiling", "wall", "floor"):
            mapped = mapper.map_scheme(part_id, scheme.feature, scheme.scheme_name)
            lines.extend(_geometry_lines(data, scheme, mapped.lines))
        if scheme is not None and part_id == "cabinetry":
            lines.extend(_run_lines(data, scheme))
        pieces, blocked = _piece_lines(data, part_id)
        lines.extend(pieces)
        unpriced.extend(blocked)
        if not lines:
            lines = [
                _line(
                    room_name="",
                    item=title,
                    unit="",
                    quantity=None,
                    craft=scheme.scheme_name if scheme else "",
                    unit_price=None,
                    amount=None,
                    remark="这个方案没有可计入小计的数量。" if scheme else "未选方案，不出计价行。",
                    included=False,
                )
            ]
        sections.append({"id": part_id, "title": title, "lines": lines})

    install_lines: list[dict] = []
    for part_id in INSTALL_PARTS:
        scheme = schemes.get(part_id)
        pieces = [pick for pick in data.picks if pick.included and pick.part_id == part_id and pick.product_status in (None, "", "confirmed")]
        if scheme is None and not pieces:
            continue
        quantity = None
        if pieces:
            quantity = money(sum((pick.quantity for pick in pieces), Decimal("0")))
        install_lines.append(
            _line(
                room_name="",
                item=f"安装·{CATEGORY_LABELS.get(part_id, part_id)}",
                unit="项",
                quantity=quantity,
                craft=scheme.scheme_name if scheme else "",
                unit_price=None,
                amount=None,
                remark=INSTALL_REMARK,
                included=False,
            )
        )
    if not install_lines:
        install_lines.append(
            _line(
                room_name="",
                item="安装",
                unit="项",
                quantity=None,
                craft="",
                unit_price=None,
                amount=None,
                remark=f"没有选中的安装项目。{INSTALL_REMARK}",
                included=False,
            )
        )
    sections.append({"id": "install", "title": "安装", "lines": install_lines})

    seq = 1
    for section in sections:
        section["subtotal"] = _section_subtotal(section["lines"])
        for line in section["lines"]:
            line["seq"] = seq
            seq += 1

    for sub in data.substitutes:
        label = f"{sub.get('room_name') or ''} {sub.get('slot_label') or sub.get('part_name') or ''}".strip()
        unpriced.append(
            {
                "item": label or "效果替代",
                "remark": EFFECT_REMARK,
                "priced": False,
                "included_in_subtotal": False,
            }
        )
    for row in data.generated:
        label = str(row.get("item") or row.get("label") or "未确认件")
        unpriced.append(
            {
                "item": label,
                "remark": UNCONFIRMED_REMARK,
                "priced": False,
                "included_in_subtotal": False,
            }
        )

    exclusions = [
        {
            "item": name,
            "unit": "",
            "quantity": None,
            "craft": "",
            "unit_price": None,
            "amount": None,
            "remark": "不含",
            "included_in_subtotal": False,
            "priced": False,
        }
        for name in EXCLUSION_ITEMS
    ]
    part_subtotal = _section_subtotal([line for section in sections for line in section["lines"]])
    closed, unclosed, missing = [], [], []
    for room in data.rooms:
        if not room.on_plan or not room.polygon:
            if room.name:
                missing.append(room.name)
            continue
        from app.services.takeoff_geometry import is_closed

        bucket = closed if is_closed(room.polygon) else unclosed
        bucket.append(room.name or "未命名")

    return {
        "institution": INSTITUTION,
        "title": f"{INSTITUTION}精装报价单",
        "selection_id": data.selection_id,
        "customer_name": data.customer_name,
        "customer_phone": data.customer_phone,
        "project_name": data.project_name,
        "project_code": data.project_code,
        "unit_name": data.unit_name,
        "style_name": data.style_name,
        "selection_quote": data.selection_quote,
        "selection_note": SELECTION_NOTE,
        "geometry_note": GEOMETRY_NOTE,
        "mapping": {
            "mode": "fixed_rules",
            "model_hook": "not_connected" if not hook.connected else "connected",
            "honesty": MAPPING_HONESTY,
        },
        "plan": {
            "id": data.plan_id,
            "filename": data.plan_filename,
            "has_scale": data.scale_m_per_unit is not None and data.scale_m_per_unit > 0,
            "scale_m_per_unit": _num(data.scale_m_per_unit),
            "wall_height_m": _num(data.wall_height_m),
            "closed_rooms": closed,
            "unclosed_rooms": unclosed,
            "missing_from_plan": missing,
            "drawing_missing": data.drawing_missing,
        },
        "sections": sections,
        "exclusions": exclusions,
        "part_subtotal": part_subtotal,
        "unpriced": unpriced,
        "rules": [
            "只量设计师已经拆开的简化平面。不读整套施工图，也不自动把缺口连上。",
            "墙线必须首尾相接才算闭合。面积用鞋带公式，周长是各边之和。",
            "米等于图面长度乘比例。平方米等于图面面积乘比例的平方。没有比例就留空。",
            "双眼皮和跌级边长等于该房间闭合墙线的周长。不估跌级宽度，平顶面积不扣边。",
            "墙面面积等于周长乘平面上写明的层高。没有层高就留空。门窗洞没标，不扣。",
            "房间没点这个部位，或平面上没有这个房间，数量留空。不用档案里的计价面积去填。",
            "一个点不是长度。件数只用客户已经勾选的数量。",
            "平方米单价只用已选方案的面积单价，一个方案只计在一道面积上。按米的边长不套这个单价。",
            "水电改造、人工、管理费、税金未计算，单列不含，不进小计。",
            "效果替代、未确认和未生成的件不计价，也不能下单。",
        ],
    }


def _as_scale(value) -> Decimal | None:
    if value is None:
        return None
    number = Decimal(str(value))
    if number <= 0:
        return None
    return number


def _drawn(db: Session, plan) -> tuple[list[DrawnRoom], bool]:
    if plan is None:
        return [], True
    asset = db.get(Asset, plan.asset_id)
    if asset is None or not asset.storage_key or asset.status != "stored":
        return [], True
    try:
        raw, _content_type = get_storage().get(asset.storage_key)
    except FileNotFoundError:
        return [], True
    name = (asset.filename or "").lower()
    if plan.media == "svg" or name.endswith(".svg"):
        return rooms_from_svg(raw.decode("utf-8", errors="replace")), False
    if plan.media == "dxf" or name.endswith(".dxf"):
        return rooms_from_dxf(raw), False
    return [], True


def _scheme_in(scheme, part_name: str) -> SchemeIn:
    material = scheme.material or {}
    price = None if scheme.unit_price is None else Decimal(str(scheme.unit_price))
    return SchemeIn(
        part_id=scheme.part_id,
        part_name=part_name,
        scheme_name=scheme.name,
        feature=str(material.get("feature") or ""),
        unit_price=price,
        pricing="area" if scheme.part_id in ALWAYS_SECTIONS else "each",
    )


def takeoff_for_selection(db: Session, selection) -> dict:
    """Read the selection and the marked plan. Does not write a quote."""
    quote = quote_dict(quote_for_selection(db, selection))
    plan = active_plan(db, selection.project_id, selection.unit_type_id)
    drawn, drawing_missing = _drawn(db, plan)
    rooms: list[RoomLoop] = []
    seen: set[str] = set()
    for item in drawn:
        rooms.append(RoomLoop(item.name, item.polygon, True))
        if item.name:
            seen.add(item.name)
    for room in selection.unit.rooms:
        if room.name in seen:
            continue
        rooms.append(RoomLoop(room.name, None, False))
        seen.add(room.name)
    marks: set[tuple[str, str]] = set()
    if plan is not None:
        for mark in plan.marks or []:
            marks.add((mark.room_name, mark.part_id))
    schemes: list[SchemeIn] = []
    used: set[str] = set()
    for part_id, scheme in (
        ("ceiling", selection.ceiling_scheme),
        ("floor", selection.floor_scheme),
        ("wall", selection.wall_scheme),
    ):
        if scheme is None:
            continue
        schemes.append(_scheme_in(scheme, CATEGORY_LABELS.get(part_id, part_id)))
        used.add(part_id)
    for line in selection.lines or []:
        if line.part_id in used or line.scheme is None:
            continue
        schemes.append(_scheme_in(line.scheme, CATEGORY_LABELS.get(line.part_id, line.part_id)))
        used.add(line.part_id)
    picks: list[PickIn] = []
    for line in selection.lines or []:
        for pick in line.picks or []:
            if pick.item is None:
                continue
            product = pick.product
            status = None if product is None else product.status
            part_id = pick.item.display_part_id or line.part_id
            price = Decimal(str(pick.item.unit_price))
            name = pick.item.name
            tier = pick.brand_tier or line.brand_tier
            if product is not None and status == "confirmed":
                chosen = product.import_price if tier == "import" else product.domestic_price
                price = Decimal(str(chosen))
                if product.model_code:
                    name = f"{name} {product.model_code}"
            craft = line.scheme.name if line.scheme is not None else name
            if tier == "import":
                craft = f"{craft}（进口）"
            elif tier == "domestic":
                craft = f"{craft}（国产）"
            picks.append(
                PickIn(
                    part_id=part_id,
                    room_name=(pick.item.room_name or line.room_or_zone or ""),
                    name=name,
                    quantity=Decimal(str(pick.quantity or 1)),
                    unit_price=price,
                    included=bool(pick.included),
                    product_status=status,
                    craft=craft,
                )
            )
    generated = [
        {"item": row.label or row.model_code or row.part_id, "status": row.status}
        for row in db.scalars(select(GeneratedCandidate).order_by(GeneratedCandidate.id)).all()
    ]
    style_name = "" if selection.style is None else selection.style.name
    return build_takeoff(
        TakeoffInput(
            selection_id=selection.id,
            customer_name=selection.customer.display_name,
            customer_phone=selection.customer.phone,
            project_name=selection.project.name,
            project_code=selection.project.code,
            unit_name=selection.unit.name,
            style_name=style_name,
            selection_quote=quote,
            scale_m_per_unit=None if plan is None else _as_scale(plan.scale_m_per_unit),
            wall_height_m=None if plan is None else _as_scale(plan.wall_height_m),
            plan_id="" if plan is None else plan.id,
            plan_filename="" if plan is None else plan.filename,
            drawing_missing=drawing_missing,
            rooms=rooms,
            marks=marks,
            schemes=schemes,
            picks=picks,
            substitutes=substitutes_for(db, selection.id),
            generated=generated,
        )
    )
