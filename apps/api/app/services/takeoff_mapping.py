"""Map a selected scheme to decoration-company lines.

The live path is the fixed rule table. ``UnconnectedModelMapper`` is the
reserved hook for a later model that only chooses which lines a scheme
corresponds to. It is not connected, it does not call a service, and it
never estimates a length or an area.
"""

from dataclasses import dataclass
from decimal import Decimal

INSTITUTION = "祺盛"

MAPPING_HONESTY = (
    "方案对应哪几条装饰公司清单，这一步留给以后的对照接口。"
    "现在没有可用的免费额度，接口未接通，不会调用模型。"
    "几何不交给模型估算。"
)

GEOMETRY_NOTE = (
    "算量按已标注简化平面的尺寸和比例，只跟这张平面一样准。"
    "缺比例、墙线不闭合或房间没标注时，数量留空，不估一个数。"
)

SELECTION_NOTE = (
    "部位合计是选配报价，按已选方案和分房计价面积计算，打印时不改这个数。"
    "下面的算量是另一张单，按简化平面的尺寸。两数不要相加。"
)

EXCLUSION_ITEMS = ("水电改造", "人工", "管理费", "税金")

# feature -> lines. Heights here are written into the scheme rule, not guessed
# from a missing storey height. 2.4 m is the 浅木护墙 scheme, feature "wainscot".
WAINSCOT_M = Decimal("2.4")


@dataclass(frozen=True)
class BreakdownLine:
    item: str
    kind: str
    unit: str
    stated_height_m: Decimal | None = None


@dataclass(frozen=True)
class MappingResult:
    connected: bool
    source: str
    lines: tuple[BreakdownLine, ...]
    honesty: str


def _lines(*rows: tuple[str, str, str] | tuple[str, str, str, Decimal]) -> tuple[BreakdownLine, ...]:
    built: list[BreakdownLine] = []
    for row in rows:
        if len(row) == 4:
            item, kind, unit, height = row
            built.append(BreakdownLine(item, kind, unit, height))
        else:
            item, kind, unit = row  # type: ignore[misc]
            built.append(BreakdownLine(item, kind, unit, None))
    return tuple(built)


_CEILING: dict[str, tuple[BreakdownLine, ...]] = {
    # Edge drop plus paint. Length is the room perimeter. Paint keeps the full area.
    "cove": _lines(("平顶乳胶漆", "area", "m²"), ("双眼皮", "perimeter", "m")),
    "gold_trough": _lines(("平顶乳胶漆", "area", "m²"), ("双眼皮", "perimeter", "m")),
    "cornice": _lines(("平顶乳胶漆", "area", "m²"), ("石膏线", "perimeter", "m")),
    # Full drop ceiling, plus the edge length of that drop.
    "tray": _lines(("跌级吊顶", "area", "m²"), ("双眼皮", "perimeter", "m")),
    "lightwell": _lines(("叠级吊顶", "area", "m²"), ("双眼皮", "perimeter", "m")),
    "medallion": _lines(("吊顶", "area", "m²"), ("石膏线", "perimeter", "m")),
    "gloss_panel": _lines(("悬浮吊顶", "area", "m²"), ("收边", "perimeter", "m")),
    "veneer": _lines(("饰面吊顶", "area", "m²")),
    "mirror_edge": _lines(("金属吊顶", "area", "m²"), ("收边", "perimeter", "m")),
}

_WALL: dict[str, tuple[BreakdownLine, ...]] = {
    "paint": _lines(("墙面乳胶漆", "wall_area", "m²")),
    "gloss": _lines(("墙面乳胶漆", "wall_area", "m²")),
    "fabric_accent": _lines(("墙面乳胶漆", "wall_area", "m²")),
    "wainscot": _lines(
        ("护墙", "stated_band", "m²", WAINSCOT_M),
        ("上部乳胶漆", "above_band", "m²", WAINSCOT_M),
    ),
    "moulding": _lines(("墙面乳胶漆", "wall_area", "m²"), ("造型线", "perimeter", "m")),
    "upholstered": _lines(("软包墙面", "wall_area", "m²")),
    "stone_full": _lines(("石材墙面", "wall_area", "m²")),
    "sintered": _lines(("岩板墙面", "wall_area", "m²")),
    "leather": _lines(("皮革墙面", "wall_area", "m²")),
}

_FLOOR: dict[str, tuple[BreakdownLine, ...]] = {
    "tile": _lines(("地面铺贴", "area", "m²")),
    "wood": _lines(("地面铺装", "area", "m²")),
    "stone": _lines(("地面铺贴", "area", "m²")),
    "marble_border": _lines(("地面铺贴", "area", "m²"), ("波打线", "perimeter", "m")),
    "parquet": _lines(("拼花地面", "area", "m²"), ("镶边", "perimeter", "m")),
    "metal_grout": _lines(("地面铺贴", "area", "m²")),
}

_TABLES = {"ceiling": _CEILING, "wall": _WALL, "floor": _FLOOR}

_FALLBACK = {
    "ceiling": _lines(("天花", "area", "m²")),
    "wall": _lines(("墙面", "wall_area", "m²")),
    "floor": _lines(("地面", "area", "m²")),
}


class FixedRuleMapper:
    """The mapper that print/review actually uses."""

    source = "fixed_rules"

    def map_scheme(self, part_id: str, feature: str, scheme_name: str = "") -> MappingResult:
        del scheme_name
        table = _TABLES.get(part_id)
        if table is None:
            return MappingResult(True, self.source, (), MAPPING_HONESTY)
        lines = table.get(feature or "")
        if lines is None:
            lines = _FALLBACK.get(part_id, ())
        return MappingResult(True, self.source, lines, MAPPING_HONESTY)


class UnconnectedModelMapper:
    """Reserved interface. Not wired to a model, a key, or a network call."""

    source = "model_hook"

    def map_scheme(self, part_id: str, feature: str, scheme_name: str = "") -> MappingResult:
        del part_id, feature, scheme_name
        return MappingResult(False, self.source, (), MAPPING_HONESTY)
