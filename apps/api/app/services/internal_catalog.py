"""Load the internal evaluation pack and the confirmed generated meshes.

Mesh files stay on disk. A missing GLB is explained, not treated as a crash.
"""

import json
import os
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GeneratedCandidate, InternalSample, WorkerJob
from app.services.image_to_3d import QUOTA_BLOCK_MESSAGE

PACK_DIR = Path(__file__).resolve().parents[4] / "packages" / "catalog" / "internal-sample"
REPO_ROOT = PACK_DIR.parents[2]
CATALOG_PATH = PACK_DIR / "catalog.json"
IMAGE_DIR = PACK_DIR / "images"
GENERATED_DIR = PACK_DIR / "generated"
MANIFEST_PATH = GENERATED_DIR / "manifest.json"
PREVIEW_DIR = GENERATED_DIR / "previews"
MESH_DIR_NAME = "生模评测"
_MESH_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}\.glb$")
_PREVIEW_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}\.png$")

DISCLAIMER = "祺盛内部样板，非授权经销清单，不对外展示、不作客户承诺。"
TEXTURE_LABEL = "示意贴图，不是品牌实拍，也不改变报价，不列入采购。"
MISSING_PUBLIC = "未找到可核验公开资料"
MADE_TO_MEASURE = "按实际尺寸定制"
MEASURE_STATUS = "量尺定制"
MODULE_STATUS = "官方类型表模块尺寸、供按实际尺寸定制对照"
GENERATION_STATUS = "首批五件已确认入库"
GENERATION_NOTE = (
    "混元图生三维的首批 5 件已经生成，并已确认进入祺盛内部样板。"
    "来源是生成件，不给客户看，不计价，不能下单。"
    "Nobilia U60 没有产品图，这件没做。"
    "免费资源包已经用尽，后付费没有开通。"
    "设计师上传图册或产品图后仍可发起下一次生模，任务会停在额度不足，不会调用付费接口，也不会生成新网格。"
)


def load_pack() -> list[dict]:
    if not CATALOG_PATH.is_file():
        return []
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def load_generated_manifest() -> dict:
    if not MANIFEST_PATH.is_file():
        return {"items": [], "skipped": []}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _brand_label(row: dict) -> str:
    brand = row.get("brand") or ""
    zh = (row.get("brand_zh") or "").strip()
    if zh and zh != brand:
        return f"{zh} / {brand}"
    return brand


def _generated_index() -> dict[str, dict]:
    manifest = load_generated_manifest()
    indexed: dict[str, dict] = {}
    for row in manifest.get("items") or []:
        code = row.get("model_code")
        if code:
            indexed[code] = row
    return indexed


def _safe_file(directory: Path, name: str, pattern: re.Pattern[str]) -> Path | None:
    if not pattern.fullmatch(name or ""):
        return None
    try:
        root = directory.resolve()
        path = (root / name).resolve()
    except OSError:
        return None
    if path != root and root not in path.parents:
        return None
    try:
        if not path.is_file():
            return None
    except OSError:
        return None
    return path


def preview_file(model_code: str | None) -> Path | None:
    if not model_code:
        return None
    return _safe_file(PREVIEW_DIR, f"{model_code}.png", _PREVIEW_NAME)


def mesh_directories() -> list[Path]:
    candidates: list[Path] = []
    env = os.environ.get("QISHENG_MESH_DIR", "").strip()
    if env:
        candidates.append(Path(env).expanduser())
    candidates.extend(
        [
            REPO_ROOT / MESH_DIR_NAME,
            PACK_DIR / MESH_DIR_NAME,
            Path.cwd() / MESH_DIR_NAME,
        ]
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def resolve_mesh(filename: str) -> tuple[Path | None, str]:
    """Find a local evaluation mesh. Missing files return an explanation and no exception."""
    safe = (filename or "").strip()
    if not _MESH_NAME.fullmatch(safe):
        return None, "网格文件名不合法，没有去读盘。预览图和入库记录不受影响。"
    checked: list[str] = []
    for directory in mesh_directories():
        try:
            root = directory.resolve()
        except OSError:
            checked.append(f"{directory}（目录读不到）")
            continue
        checked.append(str(root))
        candidate = (root / safe).resolve()
        if candidate != root and root not in candidate.parents:
            continue
        try:
            ready = candidate.is_file()
        except OSError:
            ready = False
        if ready:
            return candidate, f"已从本地评测目录读到 {safe}：{candidate}"
    note = (
        f"没有找到 {safe}。网格不提交进 git。"
        f"请把验收包解压成文件夹「{MESH_DIR_NAME}」，使其中直接有 {safe}。"
        f"可以放在仓库根目录，或设置环境变量 QISHENG_MESH_DIR 指向该文件夹。"
        f"已查找：{'；'.join(checked)}。"
        f"预览图仍可看，这不是程序错误，页面不会因此中断。"
    )
    return None, note


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


def seed_confirmed_generated(db: Session) -> int:
    """Put the five approved meshes into the internal library. Does not price or publish them."""
    pack = {row.get("model_code"): row for row in load_pack() if row.get("model_code")}
    count = 0
    for item in load_generated_manifest().get("items") or []:
        code = item.get("model_code")
        if not code:
            continue
        origin = pack.get(code) or {}
        label = _brand_label(item)
        fields = {
            "part_id": item.get("part_id") or origin.get("part_id") or "",
            "category_zh": item.get("category_zh") or origin.get("category_zh") or "",
            "brand": item.get("brand") or origin.get("brand") or "",
            "origin": origin.get("origin") or "",
            "name": origin.get("name") or f"{label} 生成件",
            "model_code": code,
            "spec": origin.get("spec"),
            "width_mm": _optional_number(origin.get("width_mm")),
            "depth_mm": _optional_number(origin.get("depth_mm")),
            "height_mm": _optional_number(origin.get("height_mm")),
            "kind": "form",
            "verified": bool(origin.get("model_code")),
            "local_image": f"{code}.png",
            "source_url": origin.get("source_url") or "",
            "source_title": origin.get("source_title") or "",
            "notes": "混元图生三维生成件，已确认进入祺盛内部样板。不给客户看，不计价，不能下单。",
            "source": "generated",
            "customer_visible": False,
            "priced": False,
            "orderable": False,
        }
        item_id = f"isample-gen-{code}"
        current = db.get(InternalSample, item_id)
        if current is None:
            db.add(InternalSample(id=item_id, **fields))
        elif current.source == "generated":
            for key, value in fields.items():
                setattr(current, key, value)
        candidate_id = f"gen-confirmed-{code}"
        candidate = db.get(GeneratedCandidate, candidate_id)
        candidate_fields = {
            "part_id": fields["part_id"],
            "brand": fields["brand"],
            "model_code": code,
            "label": f"{label} {code} 生成件",
            "status": "confirmed",
            "note": item.get("note") or fields["notes"],
        }
        if candidate is None:
            db.add(GeneratedCandidate(id=candidate_id, **candidate_fields))
        else:
            for key, value in candidate_fields.items():
                setattr(candidate, key, value)
        count += 1
    db.flush()
    return count


def image_path(row: InternalSample) -> Path | None:
    if row.source == "generated":
        return preview_file(row.model_code)
    if not row.local_image:
        return None
    path = (IMAGE_DIR / Path(row.local_image).name).resolve()
    try:
        if IMAGE_DIR.resolve() not in path.parents or not path.is_file():
            return None
    except OSError:
        return None
    return path


def sample_dict(row: InternalSample) -> dict:
    meta = _generated_index().get(row.model_code or "") if row.source == "generated" else None
    mesh_ready = False
    mesh_note = ""
    mesh_url = None
    priority = None
    brand_label = row.brand
    confirmed = False
    if row.source == "generated":
        offer_mode = "generated"
        data_status = "已确认入库 · 生成件 · 不给客户看"
        confirmed = True
        brand_label = _brand_label(meta or {"brand": row.brand})
        priority = None if meta is None else meta.get("priority")
        filename = f"{row.model_code}.glb" if row.model_code else ""
        if filename:
            _mesh, mesh_note = resolve_mesh(filename)
            mesh_ready = _mesh is not None
            mesh_url = f"/api/admin/internal-samples/{row.id}/mesh"
        else:
            mesh_note = "这件没有评测网格文件名。预览和入库记录不受影响。"
    elif row.part_id == "cabinetry" and row.source == "sample_pack":
        offer_mode = "made_to_measure"
        data_status = MODULE_STATUS if row.model_code else MEASURE_STATUS
    elif not row.verified:
        offer_mode = "unverified"
        data_status = MISSING_PUBLIC
    else:
        offer_mode = "catalog"
        data_status = "已核验"
    photo = image_path(row)
    return {
        "id": row.id,
        "part_id": row.part_id,
        "category_zh": row.category_zh,
        "brand": row.brand,
        "brand_label": brand_label,
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
        "has_image": photo is not None,
        "image_url": None if photo is None else f"/api/admin/internal-samples/{row.id}/image",
        "texture_url": None
        if row.kind != "material" or row.source != "sample_pack" or photo is None
        else f"/api/finish-textures/{row.id}/image",
        "source_url": row.source_url,
        "source_title": row.source_title,
        "notes": row.notes,
        "source": row.source,
        "confirmed": confirmed,
        "priority": priority,
        "mesh_ready": mesh_ready,
        "mesh_note": mesh_note,
        "mesh_url": mesh_url,
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


def review_rows() -> list[dict]:
    manifest = load_generated_manifest()
    rows: list[dict] = []
    for item in manifest.get("items") or []:
        rows.append(
            {
                "priority": item.get("priority"),
                "part": item.get("category_zh") or "",
                "part_id": item.get("part_id") or "",
                "brand": item.get("brand") or "",
                "brand_label": _brand_label(item),
                "model_code": item.get("model_code"),
                "status": item.get("status") or "已确认入库",
                "note": item.get("note") or "",
            }
        )
    for item in manifest.get("skipped") or []:
        rows.append(
            {
                "priority": item.get("priority"),
                "part": item.get("category_zh") or "",
                "part_id": item.get("part_id") or "",
                "brand": item.get("brand") or "",
                "brand_label": _brand_label(item),
                "model_code": item.get("model_code"),
                "status": item.get("status") or "未做",
                "note": item.get("note") or "",
            }
        )
    rows.sort(key=lambda row: row["priority"] if isinstance(row["priority"], int) else 99)
    return rows


def generation_status(db: Session) -> dict:
    pending = db.scalars(
        select(GeneratedCandidate).where(GeneratedCandidate.status == "pending").order_by(GeneratedCandidate.created_at)
    ).all()
    blocked = db.scalars(
        select(WorkerJob).where(WorkerJob.kind == "image_to_3d").order_by(WorkerJob.created_at.desc()).limit(20)
    ).all()
    return {
        "status": GENERATION_STATUS,
        "note": GENERATION_NOTE,
        "paid_api_called": False,
        "postpaid_enabled": False,
        "free_pack_exhausted": True,
        "can_generate": False,
        "quota_message": QUOTA_BLOCK_MESSAGE,
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
        "review": review_rows(),
        "attempts": [
            {
                "id": job.id,
                "status": job.status,
                "filename": (job.payload or {}).get("filename") or "",
                "part_id": (job.payload or {}).get("part_id") or "",
                "brand": (job.payload or {}).get("brand") or "",
                "model_code": (job.payload or {}).get("model_code") or "",
                "message": (job.result or {}).get("message") or QUOTA_BLOCK_MESSAGE,
                "paid_api_called": False,
                "postpaid_enabled": False,
            }
            for job in blocked
        ],
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
