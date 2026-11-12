"""Seeded simplified plan and two photo stand-ins so the demo can be opened without extra files."""

import struct
import zlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, CustomerSelection, PlanMark, PlanSheet, VisualSubstitute
from app.services.image_to_3d import default_size_mm
from app.services.plan_geometry import parse_svg
from app.services.storage import get_storage

VIEW_W = 1000
VIEW_H = 640
PLAN_ID = "plan-gz-a"
PLAN_ASSET_ID = "asset-gz-a-simple"
ROOMS: dict[str, tuple[int, int, int, int]] = {
    "玄关": (40, 470, 200, 140),
    "客厅": (40, 40, 520, 410),
    "餐厅": (260, 470, 300, 140),
    "厨房": (580, 360, 180, 250),
    "公卫": (580, 40, 180, 190),
    "过道": (580, 250, 180, 90),
    "主卧": (780, 40, 180, 300),
    "次卧": (780, 360, 180, 250),
}


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def png_rgb(width: int, height: int, painter) -> bytes:
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            row.extend(painter(x, y, width, height))
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", raw) + _chunk(b"IEND", b"")


def _inside_ellipse(x: float, y: float, cx: float, cy: float, rx: float, ry: float) -> bool:
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1


def toilet_png() -> bytes:
    def paint(x: int, y: int, width: int, height: int) -> tuple[int, int, int]:
        nx, ny = x / width, y / height
        if 0.18 < nx < 0.82 and 0.08 < ny < 0.42:
            return (236, 239, 241)
        if _inside_ellipse(nx, ny, 0.5, 0.62, 0.3, 0.22):
            return (250, 252, 252)
        if _inside_ellipse(nx, ny, 0.5, 0.64, 0.16, 0.1):
            return (196, 208, 214)
        return (244, 236, 226)

    return png_rgb(160, 120, paint)


def sofa_png() -> bytes:
    def paint(x: int, y: int, width: int, height: int) -> tuple[int, int, int]:
        nx, ny = x / width, y / height
        if nx < 0.08 or nx > 0.92:
            return (32, 64, 78)
        if ny < 0.34:
            return (214, 224, 228)
        if 0.34 <= ny < 0.42:
            return (28, 36, 42)
        stripe = int(nx * 8) % 2 == 0
        return (36, 104, 128) if stripe else (58, 132, 154)

    return png_rgb(240, 140, paint)


def point(room: str, fx: float, fy: float) -> tuple[float, float]:
    x, y, width, height = ROOMS[room]
    return (round((x + width * fx) / VIEW_W, 4), round((y + height * fy) / VIEW_H, 4))


def build_demo_svg() -> str:
    rects = []
    labels = []
    for name, (x, y, width, height) in ROOMS.items():
        rects.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="#f6f1ea" stroke="#2c2924" stroke-width="6"/>'
        )
        labels.append(
            f'<text x="{x + 14}" y="{y + 32}" font-size="26" fill="#2c2924">{name}</text>'
        )
    body = "\n".join(rects + labels)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VIEW_W} {VIEW_H}" width="{VIEW_W}" height="{VIEW_H}">'
        f'<rect width="100%" height="100%" fill="#efe6d8"/>{body}</svg>'
    )


DEMO_MARKS = (
    ("mark-living-floor", "客厅", "floor", "地面", *point("客厅", 0.5, 0.62)),
    ("mark-living-wall", "客厅", "wall", "墙面", *point("客厅", 0.08, 0.48)),
    ("mark-living-ceiling", "客厅", "ceiling", "天花", *point("客厅", 0.5, 0.24)),
    ("mark-living-light", "客厅", "lighting", "灯具", *point("客厅", 0.46, 0.36)),
    ("mark-living-sofa", "客厅", "sofa", "沙发", *point("客厅", 0.42, 0.72)),
    ("mark-living-switch", "客厅", "switch_socket", "开关插座", *point("客厅", 0.9, 0.42)),
    ("mark-bath-toilet", "公卫", "sanitary", "马桶", *point("公卫", 0.55, 0.58)),
    ("mark-entry-door", "玄关", "entry_door", "入户门", *point("玄关", 0.5, 0.72)),
    ("mark-master-cab", "主卧", "cabinetry", "柜体", *point("主卧", 0.42, 0.62)),
)


def _upsert_asset(
    db: Session,
    *,
    asset_id: str,
    project_id: str,
    unit_type_id: str | None,
    selection_id: str | None,
    kind: str,
    filename: str,
    content_type: str,
    data: bytes,
    note: str,
) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        asset = Asset(id=asset_id, project_id=project_id, status="stored")
        db.add(asset)
    key = f"assets/demo/{asset_id}/{filename}"
    get_storage().put(key, data, content_type)
    asset.project_id = project_id
    asset.unit_type_id = unit_type_id
    asset.selection_id = selection_id
    asset.kind = kind
    asset.filename = filename
    asset.content_type = content_type
    asset.byte_size = len(data)
    asset.storage_key = key
    asset.status = "stored"
    asset.note = note
    return asset


def _upsert_substitute(
    db: Session,
    *,
    substitute_id: str,
    selection_id: str,
    project_id: str,
    part_id: str,
    room_name: str,
    slot_label: str,
    png: bytes,
    filename: str,
) -> None:
    width, depth, height = default_size_mm(part_id, slot_label)
    asset_id = f"{substitute_id}-photo"
    _upsert_asset(
        db,
        asset_id=asset_id,
        project_id=project_id,
        unit_type_id=None,
        selection_id=selection_id,
        kind="effect_photo",
        filename=filename,
        content_type="image/png",
        data=png,
        note="演示用示意图，仅用于效果展示，不列入采购。不是品牌实拍。",
    )
    row = db.get(VisualSubstitute, substitute_id)
    fields = {
        "selection_id": selection_id,
        "part_id": part_id,
        "room_name": room_name,
        "slot_label": slot_label,
        "width_mm": width,
        "depth_mm": depth,
        "height_mm": height,
        "primary_asset_id": asset_id,
        "secondary_asset_id": None,
        "demo": True,
    }
    if row is None:
        db.add(VisualSubstitute(id=substitute_id, **fields))
    else:
        for key, value in fields.items():
            setattr(row, key, value)


def seed_visual_demo(db: Session, project_id: str, unit_type_id: str, selection_id: str) -> None:
    selection = db.get(CustomerSelection, selection_id)
    if selection is None:
        return
    svg = build_demo_svg().encode("utf-8")
    _upsert_asset(
        db,
        asset_id=PLAN_ASSET_ID,
        project_id=project_id,
        unit_type_id=unit_type_id,
        selection_id=None,
        kind="simplified_plan",
        filename="A户型简化平面.svg",
        content_type="image/svg+xml",
        data=svg,
        note="演示用简化平面，供人工点选。不是施工图识别结果，也没有读取 DWG 图层。",
    )
    vectors = parse_svg(svg.decode("utf-8"))
    plan = db.get(PlanSheet, PLAN_ID)
    others = db.scalars(
        select(PlanSheet).where(
            PlanSheet.unit_type_id == unit_type_id,
            PlanSheet.id != PLAN_ID,
            PlanSheet.active.is_(True),
        )
    ).all()
    fields = {
        "project_id": project_id,
        "unit_type_id": unit_type_id,
        "asset_id": PLAN_ASSET_ID,
        "filename": "A户型简化平面.svg",
        "media": "svg",
        "vectors": vectors,
        "active": len(others) == 0,
        "note": "人标、系统摆的演示底图。墙线来自这张简化图，不是 CAD 对齐。",
    }
    if plan is None:
        plan = PlanSheet(id=PLAN_ID, **fields)
        db.add(plan)
    else:
        for key, value in fields.items():
            setattr(plan, key, value)
    db.flush()
    for mark_id, room_name, part_id, slot_label, x, y in DEMO_MARKS:
        mark = db.get(PlanMark, mark_id)
        mark_fields = {
            "plan_id": PLAN_ID,
            "project_id": project_id,
            "unit_type_id": unit_type_id,
            "room_name": room_name,
            "part_id": part_id,
            "slot_label": slot_label,
            "x": x,
            "y": y,
        }
        if mark is None:
            db.add(PlanMark(id=mark_id, **mark_fields))
        else:
            for key, value in mark_fields.items():
                setattr(mark, key, value)
    _upsert_substitute(
        db,
        substitute_id="sub-demo-toilet",
        selection_id=selection_id,
        project_id=project_id,
        part_id="sanitary",
        room_name="公卫",
        slot_label="马桶",
        png=toilet_png(),
        filename="马桶-演示示意图.png",
    )
    _upsert_substitute(
        db,
        substitute_id="sub-demo-sofa",
        selection_id=selection_id,
        project_id=project_id,
        part_id="sofa",
        room_name="客厅",
        slot_label="沙发",
        png=sofa_png(),
        filename="沙发-演示示意图.png",
    )
    db.flush()
