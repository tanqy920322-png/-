from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")
REFERENCE_NOTE = "样板房硬装/软装单价按建筑面积估算，不计入本次部位报价。"


def money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def as_decimal(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass(frozen=True)
class RoomArea:
    name: str
    area_m2: Decimal
    counts_toward_finish: bool


@dataclass(frozen=True)
class PricedPart:
    part_id: str
    part_name: str
    scheme_id: str | None
    scheme_name: str | None
    unit_price: Decimal | None


@dataclass
class QuoteLine:
    part_id: str
    part_name: str
    scheme_id: str | None
    scheme_name: str | None
    unit_price: Decimal | None
    area_m2: Decimal
    amount: Decimal


@dataclass
class QuoteResult:
    finish_area_m2: Decimal
    area_basis: str
    area_note: str
    excluded_rooms: list[str] = field(default_factory=list)
    lines: list[QuoteLine] = field(default_factory=list)
    total: Decimal = Decimal("0.00")
    reference: dict = field(default_factory=dict)


def resolve_area(
    rooms: list[RoomArea],
    building_area: Decimal,
    finish_override: Decimal | None,
) -> tuple[Decimal, str, list[str], str]:
    building_area = as_decimal(building_area)
    excluded = [room.name for room in rooms if not room.counts_toward_finish]
    if rooms:
        total = sum(
            (as_decimal(room.area_m2) for room in rooms if room.counts_toward_finish),
            Decimal("0"),
        )
        if excluded:
            note = "天花、地面、墙面按室内分房面积计价，不含：" + "、".join(excluded)
        else:
            note = "天花、地面、墙面按全部分房面积计价"
        return money(total), "rooms", excluded, note
    if finish_override is not None:
        return (
            money(as_decimal(finish_override)),
            "override",
            [],
            "按户型填写的计价面积计算（尚未录入分房）",
        )
    return (
        money(building_area),
        "building",
        [],
        "尚未录入分房面积，暂按建筑面积计价",
    )


def compute_quote(
    *,
    rooms: list[RoomArea],
    building_area: Decimal,
    finish_override: Decimal | None,
    parts: list[PricedPart],
    hard_cost_per_m2: Decimal,
    soft_cost_per_m2: Decimal,
) -> QuoteResult:
    area, basis, excluded, note = resolve_area(rooms, building_area, finish_override)
    lines: list[QuoteLine] = []
    for part in parts:
        unit_price = None if part.unit_price is None else money(as_decimal(part.unit_price))
        amount = Decimal("0.00") if unit_price is None else money(unit_price * area)
        lines.append(
            QuoteLine(
                part_id=part.part_id,
                part_name=part.part_name,
                scheme_id=part.scheme_id,
                scheme_name=part.scheme_name,
                unit_price=unit_price,
                area_m2=area,
                amount=amount,
            )
        )
    total = money(sum((line.amount for line in lines), Decimal("0")))
    building = money(as_decimal(building_area))
    hard = money(as_decimal(hard_cost_per_m2))
    soft = money(as_decimal(soft_cost_per_m2))
    return QuoteResult(
        finish_area_m2=area,
        area_basis=basis,
        area_note=note,
        excluded_rooms=excluded,
        lines=lines,
        total=total,
        reference={
            "building_area_m2": building,
            "hard_cost_per_m2": hard,
            "soft_cost_per_m2": soft,
            "hard_total": money(hard * building),
            "soft_total": money(soft * building),
            "note": REFERENCE_NOTE,
        },
    )
