import hmac
import re
from decimal import Decimal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.config import get_settings
from app.constants import ASSET_EXTENSIONS, CATEGORY_LABELS, MAX_UPLOAD_BYTES, TABLE_EXTENSIONS
from app.deps import AdminDep, Db
from app.models import (
    Asset,
    CustomerSelection,
    ProcurementItem,
    ProcurementTable,
    Project,
    UnitType,
)
from app.seed import SAMPLE_CSV
from app.services.auth import create_token
from app.services.files import attachment_headers, content_type_for, safe_filename
from app.services.ids import new_id
from app.services.importer import TableImportError, parse_price_table
from app.services.serialize import price_table_dict, project_dict, selection_list_item
from app.services.storage import get_storage

router = APIRouter(prefix="/api/admin", tags=["admin"])
CODE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{1,40}")
UNIT_CODE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,20}")


class AdminLogin(BaseModel):
    username: str
    password: str


class ProjectCreate(BaseModel):
    code: str
    name: str = Field(min_length=1, max_length=200)
    developer: str = ""
    city: str = ""
    district: str = ""
    address: str = ""
    description: str = ""
    hard_cost_per_m2: float = 0
    soft_cost_per_m2: float = 0
    publish: bool = False


class ProjectPatch(BaseModel):
    name: str | None = None
    developer: str | None = None
    city: str | None = None
    district: str | None = None
    address: str | None = None
    description: str | None = None
    hard_cost_per_m2: float | None = None
    soft_cost_per_m2: float | None = None
    status: str | None = None


class UnitCreate(BaseModel):
    code: str
    name: str = Field(min_length=1, max_length=80)
    building_area_m2: float
    finish_area_m2: float | None = None
    bedrooms: int = 0
    living_rooms: int = 0
    kitchens: int = 0
    bathrooms: int = 0
    summary: str = ""


def _money(value: float) -> Decimal:
    if value < 0:
        raise HTTPException(status_code=400, detail="金额不能为负")
    return Decimal(str(value)).quantize(Decimal("0.01"))


@router.post("/login")
def login(body: AdminLogin):
    settings = get_settings()
    username_ok = hmac.compare_digest(body.username, settings.admin_username)
    password_ok = hmac.compare_digest(body.password, settings.admin_password)
    if not (username_ok and password_ok):
        raise HTTPException(status_code=401, detail="账号或密码不正确")
    return {"token": create_token(sub="admin", role="admin"), "display_name": "管理员"}


@router.get("/overview")
def overview(admin: AdminDep, db: Db):
    recent = db.scalars(
        select(CustomerSelection).order_by(CustomerSelection.updated_at.desc()).limit(8)
    ).all()
    return {
        "projects": db.scalar(select(func.count()).select_from(Project)) or 0,
        "published_projects": db.scalar(select(func.count()).select_from(Project).where(Project.status == "published")) or 0,
        "selections": db.scalar(select(func.count()).select_from(CustomerSelection)) or 0,
        "submitted_selections": db.scalar(
            select(func.count()).select_from(CustomerSelection).where(CustomerSelection.status == "submitted")
        )
        or 0,
        "procurement_tables": db.scalar(select(func.count()).select_from(ProcurementTable)) or 0,
        "procurement_items": db.scalar(select(func.count()).select_from(ProcurementItem)) or 0,
        "placeholder_drawings": db.scalar(select(func.count()).select_from(Asset).where(Asset.status == "placeholder")) or 0,
        "recent_selections": [selection_list_item(db, row) for row in recent],
    }


@router.get("/projects")
def list_projects(admin: AdminDep, db: Db):
    rows = db.scalars(select(Project).order_by(Project.created_at.desc())).all()
    return [project_dict(db, project) for project in rows]


@router.post("/projects")
def create_project(body: ProjectCreate, admin: AdminDep, db: Db):
    code = body.code.strip().upper()
    if not CODE_RE.fullmatch(code):
        raise HTTPException(status_code=400, detail="项目编号仅支持字母、数字、下划线和短横线")
    project_id = code.lower()
    if db.get(Project, project_id) is not None:
        raise HTTPException(status_code=409, detail="项目编号已存在")
    project = Project(
        id=project_id,
        code=code,
        name=body.name.strip(),
        developer=body.developer.strip(),
        city=body.city.strip(),
        district=body.district.strip(),
        address=body.address.strip(),
        description=body.description.strip(),
        status="published" if body.publish else "draft",
        hard_cost_per_m2=_money(body.hard_cost_per_m2),
        soft_cost_per_m2=_money(body.soft_cost_per_m2),
    )
    db.add(project)
    db.flush()
    return project_dict(db, project)


@router.get("/projects/{project_id}")
def get_project(project_id: str, admin: AdminDep, db: Db):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project_dict(db, project)


@router.patch("/projects/{project_id}")
def patch_project(project_id: str, body: ProjectPatch, admin: AdminDep, db: Db):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in {"draft", "published"}:
        raise HTTPException(status_code=400, detail="状态只能是草稿或已发布")
    if "name" in data:
        data["name"] = (data["name"] or "").strip()
        if not data["name"]:
            raise HTTPException(status_code=400, detail="项目名称不能为空")
    for key in ("hard_cost_per_m2", "soft_cost_per_m2"):
        if key in data and data[key] is not None:
            data[key] = _money(data[key])
    for key, value in data.items():
        setattr(project, key, value)
    db.flush()
    return project_dict(db, project)


@router.post("/projects/{project_id}/units")
def add_unit(project_id: str, body: UnitCreate, admin: AdminDep, db: Db):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    code = body.code.strip().upper()
    if not UNIT_CODE_RE.fullmatch(code):
        raise HTTPException(status_code=400, detail="户型编号格式不正确")
    if body.building_area_m2 <= 0:
        raise HTTPException(status_code=400, detail="建筑面积需要大于 0")
    unit_id = f"{project.id}-{code.lower()}"
    if db.get(UnitType, unit_id) is not None:
        raise HTTPException(status_code=409, detail="该户型编号已存在")
    summary = body.summary.strip() or f"{body.bedrooms}室{body.living_rooms}厅{body.kitchens}厨{body.bathrooms}卫"
    unit = UnitType(
        id=unit_id,
        project_id=project.id,
        code=code,
        name=body.name.strip(),
        building_area_m2=_money(body.building_area_m2),
        finish_area_override=None if body.finish_area_m2 is None else _money(body.finish_area_m2),
        bedrooms=body.bedrooms,
        living_rooms=body.living_rooms,
        kitchens=body.kitchens,
        bathrooms=body.bathrooms,
        summary=summary,
    )
    db.add(unit)
    db.flush()
    return project_dict(db, project)


@router.post("/projects/{project_id}/assets")
def upload_asset(
    project_id: str,
    admin: AdminDep,
    db: Db,
    file: UploadFile = File(...),
    kind: str = Form(...),
    unit_type_id: str | None = Form(None),
    replace_asset_id: str | None = Form(None),
    note: str = Form(""),
):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if kind not in {"floor_plan", "usage_drawing", "render", "furniture_photo", "other"}:
        raise HTTPException(status_code=400, detail="不支持的图纸类型")
    filename = safe_filename(file.filename or "file")
    extension = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if extension not in ASSET_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 DWG、PDF、PNG、JPG、WEBP")
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件是空的")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="文件超过 25MB")
    unit_id = (unit_type_id or "").strip() or None
    if unit_id is not None:
        unit = db.get(UnitType, unit_id)
        if unit is None or unit.project_id != project.id:
            raise HTTPException(status_code=400, detail="户型不属于该项目")
    content_type = content_type_for(filename, file.content_type or "application/octet-stream")
    if replace_asset_id:
        asset = db.get(Asset, replace_asset_id)
        if asset is None or asset.project_id != project.id:
            raise HTTPException(status_code=404, detail="要替换的图纸不存在")
    else:
        asset = Asset(id=new_id("asset"), project_id=project.id, status="placeholder")
        db.add(asset)
    asset.unit_type_id = unit_id if unit_id is not None else asset.unit_type_id
    asset.kind = kind
    asset.filename = filename
    asset.content_type = content_type
    asset.byte_size = len(data)
    asset.storage_key = f"assets/{asset.id}/{filename}"
    asset.status = "stored"
    if note.strip():
        asset.note = note.strip()
    get_storage().put(asset.storage_key, data, content_type)
    db.flush()
    return project_dict(db, project)


@router.get("/procurement/sample.csv")
def sample_csv(admin: AdminDep):
    return Response(
        content=SAMPLE_CSV.read_bytes(),
        media_type="text/csv; charset=utf-8",
        headers=attachment_headers("sample_sanitary.csv", "sample.csv"),
    )


@router.get("/procurement/tables")
def list_tables(admin: AdminDep, db: Db):
    tables = db.scalars(select(ProcurementTable).order_by(ProcurementTable.created_at.desc())).all()
    result = []
    for table in tables:
        count = db.scalar(
            select(func.count()).select_from(ProcurementItem).where(ProcurementItem.table_id == table.id)
        ) or 0
        result.append(price_table_dict(table, int(count)))
    return result


@router.get("/procurement/tables/{table_id}")
def get_table(table_id: str, admin: AdminDep, db: Db):
    table = db.get(ProcurementTable, table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="价表不存在")
    items = db.scalars(select(ProcurementItem).where(ProcurementItem.table_id == table.id)).all()
    return price_table_dict(table, len(items), items)


@router.post("/procurement/import")
def import_table(
    admin: AdminDep,
    db: Db,
    file: UploadFile = File(...),
    category: str = Form(...),
    title: str = Form(""),
    project_id: str | None = Form(None),
):
    if category not in CATEGORY_LABELS:
        raise HTTPException(status_code=400, detail="请选择价表品类")
    filename = safe_filename(file.filename or "prices.csv")
    extension = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if extension not in TABLE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 CSV 或 XLSX")
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件是空的")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="文件超过 25MB")
    linked_project = (project_id or "").strip() or None
    if linked_project is not None and db.get(Project, linked_project) is None:
        raise HTTPException(status_code=400, detail="关联项目不存在")
    try:
        rows = parse_price_table(filename, data, category)
    except TableImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    table = ProcurementTable(
        id=new_id("price"),
        project_id=linked_project,
        category=category,
        title=(title or filename).strip()[:200],
        original_filename=filename,
    )
    db.add(table)
    db.flush()
    items = []
    for row in rows:
        item = ProcurementItem(id=new_id("sku"), table_id=table.id, **row)
        db.add(item)
        items.append(item)
    db.flush()
    return price_table_dict(table, len(items), items)


@router.get("/selections")
def list_selections(admin: AdminDep, db: Db, project_id: str | None = None):
    stmt = select(CustomerSelection).order_by(CustomerSelection.updated_at.desc())
    if project_id:
        stmt = stmt.where(CustomerSelection.project_id == project_id)
    rows = db.scalars(stmt.limit(200)).all()
    return [selection_list_item(db, row) for row in rows]
