"""Measure a designer-disassembled plan. Fixed rules only. No model.

The input is a simplified plan that already has closed wall loops, plus an
explicit scale in metres per drawing unit. This module does not read a full
construction set, does not close a gap, and does not borrow a room area from
the selection quote.

Rules
-----
1. A loop is closed only when the first and last points match within
   ``CLOSE_EPS`` drawing units. Anything else has no area and no perimeter.
2. Metres = drawing length × ``scale_m_per_unit``. Square metres = drawing
   area × scale². Missing, zero, or negative scale leaves every metre blank.
3. Area is the shoelace of the closed loop. Perimeter is the sum of its edges,
   counting the repeated closing point once.
4. 双眼皮, 跌级边, 石膏线, and other edge lengths use that same perimeter.
   The drawing does not state a drop width, so the flat area is not reduced.
5. Wall area is perimeter × a storey height written on the plan. No height,
   no wall area. Door and window openings are not deducted, because this plan
   does not mark them, and a width is not invented.
6. A one-point mark is not a length. An open run is a length only when it has
   at least two points and a scale.
7. Results are rounded half-up to 0.01. The same points and scale always
   return the same numbers.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")
CLOSE_EPS = Decimal("0.0001")

MISSING_SCALE = "平面未标明比例，未把图面尺寸换算成米"
UNCLOSED = "墙线未闭合，未计算长度和面积"
UNMARKED = "该房间未标注此部位"
NOT_ON_PLAN = "平面上没有这个房间的闭合墙线"
UNNAMED = "平面上有闭合墙线，但没有房间名"
POINT_ONLY = "只有落点，没有可量的长度"
NO_HEIGHT = "未标明层高，墙面面积未计算"
NO_VECTOR = "底图不是带尺寸的矢量闭合墙线，长度和面积留空"


def q2(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def D(value: Decimal | int | float | str | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def scale_ok(scale_m_per_unit: Decimal | int | float | str | None) -> Decimal | None:
    scale = D(scale_m_per_unit)
    if scale is None or scale <= 0:
        return None
    return scale


@dataclass(frozen=True)
class Measure:
    quantity: Decimal | None
    reasons: tuple[str, ...]

    @property
    def blank(self) -> bool:
        return self.quantity is None


def _near(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= CLOSE_EPS


def _points(polygon: list[tuple[float, float]] | None) -> list[tuple[Decimal, Decimal]] | None:
    if not polygon:
        return None
    return [(D(x), D(y)) for x, y in polygon]  # type: ignore[misc]


def is_closed(polygon: list[tuple[float, float]] | None) -> bool:
    points = _points(polygon)
    if points is None or len(points) < 4:
        return False
    return _near(points[0][0], points[-1][0]) and _near(points[0][1], points[-1][1])


def _ring(points: list[tuple[Decimal, Decimal]]) -> list[tuple[Decimal, Decimal]] | None:
    if len(points) < 4:
        return None
    if not (_near(points[0][0], points[-1][0]) and _near(points[0][1], points[-1][1])):
        return None
    return points[:-1]


def _shoelace(ring: list[tuple[Decimal, Decimal]]) -> Decimal:
    total = Decimal("0")
    count = len(ring)
    for index, (x1, y1) in enumerate(ring):
        x2, y2 = ring[(index + 1) % count]
        total += x1 * y2 - x2 * y1
    return abs(total) / Decimal("2")


def _perimeter(ring: list[tuple[Decimal, Decimal]]) -> Decimal:
    total = Decimal("0")
    count = len(ring)
    for index, (x1, y1) in enumerate(ring):
        x2, y2 = ring[(index + 1) % count]
        total += ((x2 - x1) ** 2 + (y2 - y1) ** 2).sqrt()
    return total


def _open_length(points: list[tuple[Decimal, Decimal]]) -> Decimal:
    total = Decimal("0")
    for index in range(len(points) - 1):
        x1, y1 = points[index]
        x2, y2 = points[index + 1]
        total += ((x2 - x1) ** 2 + (y2 - y1) ** 2).sqrt()
    return total


def room_area(polygon: list[tuple[float, float]] | None, scale_m_per_unit) -> Measure:
    scale = scale_ok(scale_m_per_unit)
    points = _points(polygon)
    if points is None or _ring(points) is None:
        return Measure(None, (UNCLOSED,))
    if scale is None:
        return Measure(None, (MISSING_SCALE,))
    drawing = _shoelace(_ring(points))  # type: ignore[arg-type]
    return Measure(q2(drawing * scale * scale), ())


def room_perimeter(polygon: list[tuple[float, float]] | None, scale_m_per_unit) -> Measure:
    """Closed-wall perimeter. Also the 双眼皮 / edge-drop length."""
    scale = scale_ok(scale_m_per_unit)
    points = _points(polygon)
    if points is None or _ring(points) is None:
        return Measure(None, (UNCLOSED,))
    if scale is None:
        return Measure(None, (MISSING_SCALE,))
    drawing = _perimeter(_ring(points))  # type: ignore[arg-type]
    return Measure(q2(drawing * scale), ())


def wall_area(polygon: list[tuple[float, float]] | None, scale_m_per_unit, wall_height_m) -> Measure:
    edge = room_perimeter(polygon, scale_m_per_unit)
    height = D(wall_height_m)
    reasons = list(edge.reasons)
    if height is None or height <= 0:
        reasons.append(NO_HEIGHT)
    if reasons or edge.quantity is None:
        # Keep the order stable and drop duplicates.
        seen: list[str] = []
        for reason in reasons:
            if reason not in seen:
                seen.append(reason)
        return Measure(None, tuple(seen))
    return Measure(q2(edge.quantity * height), ())  # type: ignore[operator]


def band_area(
    polygon: list[tuple[float, float]] | None,
    scale_m_per_unit,
    band_height_m,
) -> Measure:
    """A scheme-stated band (for example 护墙 2.4 m) times the closed perimeter."""
    edge = room_perimeter(polygon, scale_m_per_unit)
    height = D(band_height_m)
    if edge.quantity is None:
        return edge
    if height is None or height <= 0:
        return Measure(None, ("方案没有写明这段高度，面积留空",))
    return Measure(q2(edge.quantity * height), ())


def area_above_band(
    polygon: list[tuple[float, float]] | None,
    scale_m_per_unit,
    wall_height_m,
    band_height_m,
) -> Measure:
    edge = room_perimeter(polygon, scale_m_per_unit)
    storey = D(wall_height_m)
    band = D(band_height_m)
    reasons = list(edge.reasons)
    if storey is None or storey <= 0:
        reasons.append(NO_HEIGHT)
    if reasons or edge.quantity is None or band is None:
        seen: list[str] = []
        for reason in reasons:
            if reason not in seen:
                seen.append(reason)
        return Measure(None, tuple(seen or (NO_HEIGHT,)))
    if storey <= band:
        return Measure(None, ("标明层高不超过这段高度，上部面积留空",))
    return Measure(q2(edge.quantity * (storey - band)), ())


def open_run(points: list[tuple[float, float]] | None, scale_m_per_unit) -> Measure:
    scale = scale_ok(scale_m_per_unit)
    raw = _points(points)
    if raw is None or len(raw) < 2:
        return Measure(None, (POINT_ONLY,))
    if scale is None:
        return Measure(None, (MISSING_SCALE,))
    return Measure(q2(_open_length(raw) * scale), ())


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _as_float(value: str | None) -> float | None:
    if value is None or value == "" or "%" in value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _rect_loop(x: float, y: float, width: float, height: float) -> list[tuple[float, float]]:
    return [(x, y), (x + width, y), (x + width, y + height), (x, y + height), (x, y)]


def _pairs(text: str) -> list[tuple[str, str]]:
    rows = text.splitlines()
    pairs: list[tuple[str, str]] = []
    index = 0
    while index + 1 < len(rows):
        pairs.append((rows[index].strip(), rows[index + 1].strip()))
        index += 2
    return pairs


@dataclass(frozen=True)
class DrawnRoom:
    name: str
    polygon: list[tuple[float, float]] | None
    on_plan: bool = True


def rooms_from_svg(text: str) -> list[DrawnRoom]:
    """Closed rooms from a simplified SVG. Names come from text inside the loop.

    A full-canvas background rect is skipped. Percent sizes are skipped.
    Polygons that are not explicitly closed stay unclosed and keep no area.
    """
    from xml.etree import ElementTree as ET

    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    view_box = (root.get("viewBox") or "").replace(",", " ").split()
    canvas: tuple[float, float] | None = None
    if len(view_box) == 4:
        width = _as_float(view_box[2])
        height = _as_float(view_box[3])
        if width and height:
            canvas = (width, height)
    loops: list[list[tuple[float, float]]] = []
    labels: list[tuple[float, float, str]] = []
    for element in root.iter():
        tag = _local(element.tag)
        if tag == "rect":
            x = _as_float(element.get("x") or "0")
            y = _as_float(element.get("y") or "0")
            width = _as_float(element.get("width"))
            height = _as_float(element.get("height"))
            if None in (x, y, width, height) or width <= 0 or height <= 0:
                continue
            if canvas and width >= canvas[0] - 1 and height >= canvas[1] - 1:
                continue
            loops.append(_rect_loop(x, y, width, height))
        elif tag == "polygon":
            bits = (element.get("points") or "").replace(",", " ").split()
            points: list[tuple[float, float]] = []
            index = 0
            while index + 1 < len(bits):
                px = _as_float(bits[index])
                py = _as_float(bits[index + 1])
                if px is None or py is None:
                    break
                points.append((px, py))
                index += 2
            if len(points) >= 3 and points[0] != points[-1]:
                # Not closed on the drawing. Keep it open so the measure stays blank.
                loops.append(points)
            elif len(points) >= 4:
                loops.append(points)
        elif tag == "text":
            name = "".join(element.itertext()).strip()
            x = _as_float(element.get("x"))
            y = _as_float(element.get("y"))
            if name and x is not None and y is not None:
                labels.append((x, y, name))
    rooms: list[DrawnRoom] = []
    for loop in loops:
        name = ""
        if is_closed(loop):
            holders = [(x, y, label) for x, y, label in labels if point_in_ring(x, y, loop)]
            if holders:
                name = holders[0][2]
        rooms.append(DrawnRoom(name=name, polygon=loop, on_plan=True))
    return rooms


def rooms_from_dxf(data: bytes) -> list[DrawnRoom]:
    """Closed LWPOLYLINE loops in drawing units. Unclosed chains stay unclosed.

    LINE endpoints are chained only when they already meet. A gap is not filled.
    Binary DXF and DWG are left unread. Room names are not invented.
    """
    if data.startswith(b"AutoCAD Binary DXF"):
        return []
    text = None
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None or "SECTION" not in text.upper():
        return []
    in_entities = False
    expect_section = False
    entity = ""
    buf: dict = {}
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    polylines: list[list[tuple[float, float]]] = []

    def flush() -> None:
        nonlocal entity, buf
        if entity == "LINE" and all(key in buf for key in ("x1", "y1", "x2", "y2")):
            segments.append(((buf["x1"], buf["y1"]), (buf["x2"], buf["y2"])))
        elif entity == "LWPOLYLINE" and len(buf.get("verts") or []) >= 2:
            verts = list(buf["verts"])
            closed_flag = int(buf.get("flag") or 0)
            if closed_flag & 1 and verts[0] != verts[-1]:
                verts.append(verts[0])
            polylines.append(verts)
        entity = ""
        buf = {}

    for code, value in _pairs(text):
        if code == "0" and value == "SECTION":
            expect_section = True
            continue
        if expect_section and code == "2":
            in_entities = value.upper() == "ENTITIES"
            expect_section = False
            continue
        if code == "0" and value == "ENDSEC":
            if in_entities:
                flush()
            in_entities = False
            continue
        if not in_entities:
            continue
        if code == "0":
            flush()
            entity = value.upper()
            buf = {"verts": []}
            continue
        number = _as_float(value)
        if entity == "LINE" and number is not None:
            if code == "10":
                buf["x1"] = number
            elif code == "20":
                buf["y1"] = number
            elif code == "11":
                buf["x2"] = number
            elif code == "21":
                buf["y2"] = number
        elif entity == "LWPOLYLINE":
            if code == "70" and number is not None:
                buf["flag"] = int(number)
            elif code == "10" and number is not None:
                buf["pending_x"] = number
            elif code == "20" and number is not None and "pending_x" in buf:
                buf["verts"].append((buf.pop("pending_x"), number))
    if in_entities:
        flush()
    rooms = [DrawnRoom(name="", polygon=line, on_plan=True) for line in polylines]
    rooms.extend(_chains(segments))
    return rooms


def _same_point(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return abs(a[0] - b[0]) <= float(CLOSE_EPS) and abs(a[1] - b[1]) <= float(CLOSE_EPS)


def _chains(segments: list[tuple[tuple[float, float], tuple[float, float]]]) -> list[DrawnRoom]:
    pending = list(segments)
    rooms: list[DrawnRoom] = []
    while pending:
        start, end = pending.pop(0)
        chain = [start, end]
        grew = True
        while grew:
            grew = False
            for index, (left, right) in enumerate(pending):
                if _same_point(chain[-1], left):
                    chain.append(right)
                elif _same_point(chain[-1], right):
                    chain.append(left)
                elif _same_point(chain[0], right):
                    chain.insert(0, left)
                elif _same_point(chain[0], left):
                    chain.insert(0, right)
                else:
                    continue
                pending.pop(index)
                grew = True
                break
        if len(chain) >= 4 and _same_point(chain[0], chain[-1]) and chain[0] != chain[-1]:
            chain[-1] = chain[0]
        # Open chains stay open so the measure reports 墙线未闭合.
        rooms.append(DrawnRoom(name="", polygon=chain, on_plan=True))
    return rooms


def point_in_ring(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    points = _points(polygon)
    if points is None:
        return False
    ring = _ring(points) or points
    if len(ring) < 3:
        return False
    inside = False
    px, py = D(x), D(y)
    count = len(ring)
    for index, (x1, y1) in enumerate(ring):
        x2, y2 = ring[(index + 1) % count]
        if (y1 > py) != (y2 > py):
            cross = (x2 - x1) * (py - y1) / (y2 - y1) + x1
            if px < cross:
                inside = not inside
    return inside
