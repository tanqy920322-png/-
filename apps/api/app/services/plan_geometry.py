"""Pull simple outlines from an SVG or ASCII DXF. This is not a DWG layer parser."""

from xml.etree import ElementTree as ET


def _as_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _normalize(
    polylines: list[list[tuple[float, float]]],
    *,
    flip_y: bool = False,
    bounds: tuple[float, float, float, float] | None = None,
) -> list[list[list[float]]]:
    points = [point for line in polylines for point in line]
    if not points:
        return []
    if bounds is None:
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        pad_x = max(max_x - min_x, 1e-6) * 0.04
        pad_y = max(max_y - min_y, 1e-6) * 0.04
        min_x -= pad_x
        max_x += pad_x
        min_y -= pad_y
        max_y += pad_y
    else:
        min_x, min_y, max_x, max_y = bounds
    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)

    def nx(value: float) -> float:
        return round((value - min_x) / span_x, 4)

    def ny(value: float) -> float:
        ratio = (value - min_y) / span_y
        if flip_y:
            ratio = 1 - ratio
        return round(ratio, 4)

    cleaned: list[list[list[float]]] = []
    for line in polylines:
        if len(line) < 2:
            continue
        cleaned.append([[nx(x), ny(y)] for x, y in line])
    return cleaned


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _points_attr(text: str) -> list[tuple[float, float]]:
    bits = text.replace(",", " ").split()
    points: list[tuple[float, float]] = []
    index = 0
    while index + 1 < len(bits):
        x = _as_float(bits[index])
        y = _as_float(bits[index + 1])
        if x is None or y is None:
            break
        points.append((x, y))
        index += 2
    return points


def parse_svg(text: str) -> list[list[list[float]]]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    view_box = (root.get("viewBox") or "").replace(",", " ").split()
    bounds = None
    if len(view_box) == 4:
        origin_x = _as_float(view_box[0])
        origin_y = _as_float(view_box[1])
        width = _as_float(view_box[2])
        height = _as_float(view_box[3])
        if None not in (origin_x, origin_y, width, height) and width and height:
            bounds = (origin_x, origin_y, origin_x + width, origin_y + height)
    polylines: list[list[tuple[float, float]]] = []
    for element in root.iter():
        tag = _local(element.tag)
        if tag == "line":
            x1, y1 = _as_float(element.get("x1")), _as_float(element.get("y1"))
            x2, y2 = _as_float(element.get("x2")), _as_float(element.get("y2"))
            if None not in (x1, y1, x2, y2):
                polylines.append([(x1, y1), (x2, y2)])
        elif tag == "rect":
            x, y = _as_float(element.get("x") or "0"), _as_float(element.get("y") or "0")
            width, height = _as_float(element.get("width")), _as_float(element.get("height"))
            if None in (x, y, width, height) or width <= 0 or height <= 0:
                continue
            polylines.append([(x, y), (x + width, y), (x + width, y + height), (x, y + height), (x, y)])
        elif tag in {"polyline", "polygon"}:
            points = _points_attr(element.get("points") or "")
            if tag == "polygon" and len(points) >= 3 and points[0] != points[-1]:
                points = [*points, points[0]]
            if len(points) >= 2:
                polylines.append(points)
    return _normalize(polylines, bounds=bounds)


def _pairs(text: str) -> list[tuple[str, str]]:
    rows = text.splitlines()
    pairs: list[tuple[str, str]] = []
    index = 0
    while index + 1 < len(rows):
        pairs.append((rows[index].strip(), rows[index + 1].strip()))
        index += 2
    return pairs


def parse_dxf(data: bytes) -> tuple[list[list[list[float]]], str]:
    """Return normalized polylines and a short status.

    Binary DXF and full DWG are left unread on purpose.
    """
    if data.startswith(b"AutoCAD Binary DXF"):
        return [], "binary"
    text = None
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None or "SECTION" not in text.upper():
        return [], "unreadable"
    in_entities = False
    expect_section = False
    entity = ""
    buf: dict = {}
    polylines: list[list[tuple[float, float]]] = []

    def flush() -> None:
        nonlocal entity, buf
        if entity == "LINE" and all(key in buf for key in ("x1", "y1", "x2", "y2")):
            polylines.append([(buf["x1"], buf["y1"]), (buf["x2"], buf["y2"])])
        elif entity == "LWPOLYLINE" and len(buf.get("verts") or []) >= 2:
            polylines.append(list(buf["verts"]))
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
        if entity == "LINE":
            number = _as_float(value)
            if number is None:
                continue
            if code == "10":
                buf["x1"] = number
            elif code == "20":
                buf["y1"] = number
            elif code == "11":
                buf["x2"] = number
            elif code == "21":
                buf["y2"] = number
        elif entity == "LWPOLYLINE":
            number = _as_float(value)
            if number is None:
                continue
            if code == "10":
                buf["pending_x"] = number
            elif code == "20" and "pending_x" in buf:
                buf["verts"].append((buf.pop("pending_x"), number))
    if in_entities:
        flush()
    if not polylines:
        return [], "empty"
    return _normalize(polylines, flip_y=True), "ok"
