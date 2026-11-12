"""Load the internal evaluation pack. Values are copied from the pack, not invented."""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GeneratedCandidate, InternalSample

PACK_DIR = Path(__file__).resolve().parents[4] / "packages" / "catalog" / "internal-sample"
CATALOG_PATH = PACK_DIR / "catalog.json"
IMAGE_DIR = PACK_DIR / "images"

DISCLAIMER = "祺盛内部样板，非授权经销清单，不对外展示、不作客户承诺。"
TEXTURE_LABEL = "示意贴图，不是品牌实拍，也不改变报价，不列入采购。"
MISSING_PUBLIC = "未找到可核验公开资料"
MADE_TO_MEASURE = "按实际尺寸定制"
MEASURE_STATUS = "量尺定制"
MODULE_STATUS = "官方类型表模块尺寸、供按实际尺寸定制对照"
GENERATION_STATUS = "未完成"
GENERATION_NOTE = (
    "生模未完成。目前没有可用的免费图生三维额度，也没有接任何付费接口。"
    "下面六件只是待评清单，状态都是「未接免费接口」。"
    "确认入库队列留着，本轮没有任何已生成的模型。"
    "客户点选不会调用生模。"
)

# The six form pieces named in the pack for a later free evaluation. No meshes are produced here.
REVIEW_QUEUE = (
    {"priority": 1, "part": "洁具", "part_id": "sanitary", "brand": "恒洁", "model_code": "HC0508PT", "status": "未接免费接口"},
    {"priority": 2, "part": "洁具", "part_id": "sanitary", "brand": "TOTO", "model_code": "CW887REBTM", "status": "未接免费接口"},
    {"priority": 3, "part": "开关插座", "part_id": "switch_socket", "brand": "Schneider", "model_code": "E8331L1_DG", "status": "未接免费接口"},
    {"priority": 4, "part": "灯具", "part_id": "lighting", "brand": "雷士", "model_code": "NXXY1157", "status": "未接免费接口"},
    {"priority": 5, "part": "入户门", "part_id": "entry_door", "brand": "美心", "model_code": "CX23", "status": "未接免费接口"},
    {
        "priority": 6,
        "part": "全屋定制",
        "part_id": "cabinetry",
        "brand": "Nobilia",
        "model_code": "U60",
        "status": "未接免费接口",
        "note": "按实际尺寸定制。U60 只作官方类型表模块尺寸对照，不是单一零售型号。",
    },
)


def load_pack() -> list[dict]:
    if not CATALOG_PATH.is_file():
        return []
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def sample_id(index: int) -> str:
    return f"isample-{index:02d}"


def _optional_number(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def seed_internal_samples(db: Session) -> int:
    rows = load_pack()
    for index, row in enumerate(rows, start=1):
        code = row.get("model_code")
        verified = bool(code)
        local_name = Path(row["local_image"]).name if row.get("local_image") else None
        if local_name and not (IMAGE_DIR / local_name).is_file():
            local_name = None
        fields = {
            "part_id": row["part_id"],
            "category_zh": row.get("category_zh") or "",
            "brand": row["brand"],
            "origin": row.get("origin") or "",
            "name": row.get("name"),
            "model_code": code,
            "spec": row.get("spec"),
            "width_mm": _optional_number(row.get("width_mm")),
            "depth_mm": _optional_number(row.get("depth_mm")),
            "height_mm": _optional_number(row.get("height_mm")),
            "kind": row.get("kind") or "form",
            "verified": verified,
            "local_image": local_name,
            "source_url": row.get("source_url") or "",
            "source_title": row.get("source_title") or "",
            "notes": row.get("notes") or "",
            "source": "sample_pack",
            "customer_visible": False,
            "priced": False,
            "orderable": False,
        }
        item_id = sample_id(index)
        current = db.get(InternalSample, item_id)
        if current is None:
            db.add(InternalSample(id=item_id, **fields))
        elif current.source == "sample_pack":
            for key, value in fields.items():
                setattr(current, key, value)
    db.flush()
    return len(rows)


def image_path(row: InternalSample) -> Path | None:
    if not row.local_image:
        return None
    path = (IMAGE_DIR / Path(row.local_image).name).resolve()
    if IMAGE_DIR.resolve() not in path.parents or not path.is_file():
        return None
    return path


def sample_dict(row: InternalSample) -> dict:
    if row.part_id == "cabinetry" and row.source == "sample_pack":
        offer_mode = "made_to_measure"
        data_status = MODULE_STATUS if row.model_code else MEASURE_STATUS
    elif not row.verified:
        offer_mode = "unverified"
        data_status = MISSING_PUBLIC
    else:
        offer_mode = "catalog"
        data_status = "已核验"
    return {
        "id": row.id,
        "part_id": row.part_id,
        "category_zh": row.category_zh,
        "brand": row.brand,
        "origin": row.origin,
        "name": row.name,
        "model_code": row.model_code,
        "spec": row.spec,
        "width_mm": row.width_mm,
        "depth_mm": row.depth_mm,
        "height_mm": row.height_mm,
        "kind": row.kind,
        "verified": bool(row.verified),
        "offer_mode": offer_mode,
        "data_status": data_status,
        "has_image": image_path(row) is not None,
        "image_url": None if image_path(row) is None else f"/api/admin/internal-samples/{row.id}/image",
        "texture_url": None
        if row.kind != "material" or image_path(row) is None
        else f"/api/finish-textures/{row.id}/image",
        "source_url": row.source_url,
        "source_title": row.source_title,
        "notes": row.notes,
        "source": row.source,
        "customer_visible": False,
        "priced": False,
        "orderable": False,
        "disclaimer": DISCLAIMER,
    }


def list_samples(db: Session) -> list[InternalSample]:
    return list(db.scalars(select(InternalSample).order_by(InternalSample.id)).all())


def texture_catalog(db: Session) -> dict:
    rows = [
        sample_dict(row)
        for row in list_samples(db)
        if row.kind == "material" and row.source == "sample_pack" and image_path(row) is not None
    ]
    return {"label": TEXTURE_LABEL, "disclaimer": DISCLAIMER, "items": rows}


def generation_status(db: Session) -> dict:
    pending = db.scalars(
        select(GeneratedCandidate).where(GeneratedCandidate.status == "pending").order_by(GeneratedCandidate.created_at)
    ).all()
    return {
        "status": GENERATION_STATUS,
        "note": GENERATION_NOTE,
        "paid_api_called": False,
        "queue": [
            {
                "id": row.id,
                "part_id": row.part_id,
                "brand": row.brand,
                "model_code": row.model_code,
                "label": row.label,
                "status": row.status,
                "note": row.note,
                "customer_visible": False,
                "priced": False,
            }
            for row in pending
        ],
        "review": list(REVIEW_QUEUE),
    }


def confirm_candidate(db: Session, row: GeneratedCandidate) -> InternalSample:
    """Move a queued row into the internal library. Does not price it or show it to customers."""
    item_id = f"isample-gen-{row.id}"
    sample = db.get(InternalSample, item_id)
    fields = {
        "part_id": row.part_id or "sanitary",
        "category_zh": "",
        "brand": row.brand or "",
        "origin": "",
        "name": row.label or "生成示意件",
        "model_code": row.model_code,
        "spec": None,
        "width_mm": None,
        "depth_mm": None,
        "height_mm": None,
        "kind": "form",
        "verified": False,
        "local_image": None,
        "source_url": "",
        "source_title": "",
        "notes": "生成示意件。仅用于效果展示，不列入采购。须人工确认后才留在内部样板。",
        "source": "generated",
        "customer_visible": False,
        "priced": False,
        "orderable": False,
    }
    if sample is None:
        sample = InternalSample(id=item_id, **fields)
        db.add(sample)
    else:
        for key, value in fields.items():
            setattr(sample, key, value)
    row.status = "confirmed"
    db.flush()
    return sample
