import json
from decimal import Decimal
from pathlib import Path

from app.services.quote import PricedPart, RoomArea, compute_quote

CATALOG = Path(__file__).resolve().parents[3] / "packages" / "catalog" / "catalog.json"


def _rooms(payload):
    return [
        RoomArea(room["name"], Decimal(str(room["area_m2"])), bool(room["counts_toward_finish"]))
        for room in payload["rooms"]
    ]


def _quote(unit, prices):
    parts = [
        PricedPart("ceiling", "天花", "c", "c", Decimal(prices[0])),
        PricedPart("floor", "地面", "f", "f", Decimal(prices[1])),
        PricedPart("wall", "墙面", "w", "w", Decimal(prices[2])),
    ]
    return compute_quote(
        rooms=_rooms(unit),
        building_area=Decimal(str(unit["building_area_m2"])),
        finish_override=None,
        parts=parts,
        hard_cost_per_m2=Decimal("2500"),
        soft_cost_per_m2=Decimal("3500"),
    )


def test_catalog_finish_areas_and_default_quotes():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = {unit["code"]: unit for unit in catalog["unit_types"]}
    cream = _quote(units["A"], (180, 168, 85))
    assert cream.finish_area_m2 == Decimal("60.60")
    assert cream.excluded_rooms == ["生活阳台"]
    assert cream.total == Decimal("26239.80")
    assert cream.reference["hard_total"] == Decimal("215000.00")
    assert cream.reference["soft_total"] == Decimal("301000.00")

    luxury = _quote(units["A"], (240, 218, 95))
    assert luxury.total == Decimal("33511.80")

    european_b = _quote(units["B"], (220, 258, 145))
    assert european_b.finish_area_m2 == Decimal("69.60")
    assert european_b.excluded_rooms == ["生活阳台"]
    assert european_b.total == Decimal("43360.80")
    assert european_b.reference["building_area_m2"] == Decimal("96.00")


def test_override_used_only_when_rooms_missing():
    result = compute_quote(
        rooms=[],
        building_area=Decimal("90"),
        finish_override=Decimal("40"),
        parts=[PricedPart("ceiling", "天花", "c", "c", Decimal("100"))],
        hard_cost_per_m2=Decimal("0"),
        soft_cost_per_m2=Decimal("0"),
    )
    assert result.area_basis == "override"
    assert result.total == Decimal("4000.00")
