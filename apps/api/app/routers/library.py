from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.deps import AdminDep, Db
from app.models import CatalogProduct, LibraryModel, Part, Project, ProjectBinding, UnitType, WorkerJob
from app.services.catalog_import import ImportError, parse_manual
from app.services.ids import new_id
from app.services.product_art import example_svg
from app.services.sample_pack import SAMPLES, build_image_zip, build_manual_pdf
from app.services.sizes import size_for
from app.services.storage import get_storage

router = APIRouter(tags=["library"])
MODEL_FORMATS = {"glb", "gltf", "fbx", "obj"}


def product_dict(row: CatalogProduct) -> dict:
    return {
        "id": row.id,
        "part_id": row.part_id,
        "brand": row.brand,
        "model_code": row.model_code,
        "name": row.name,
        "spec": row.spec,
        "width_mm": row.width_mm,
        "depth_mm": row.depth_mm,
        "height_mm": row.height_mm,
        "domestic_price": float(row.domestic_price),
        "import_price": float(row.import_price),
        "status": row.status,
        "example": bool(row.example),
        "source": row.source,
        "note": row.note,
        "image_url": f"/api/products/{row.id}/image.svg",
    }


def binding_dict(row: ProjectBinding) -> dict:
    product = row.product
    return {
        "id": row.id,
        "project_id": row.project_id,
        "unit_type_id": row.unit_type_id,
        "room_name": row.room_name or "",
        "part_id": row.part_id,
        "product_id": row.product_id,
        "note": row.note,
        "product_name": "" if product is None else product.name,
        "product": None if product is None else product_dict(product),
    }


@router.get("/api/products")
def list_products(db: Db, part_id: str | None = None, q: str | None = None):
    query = select(CatalogProduct).where(CatalogProduct.status == "confirmed").order_by(CatalogProduct.part_id, CatalogProduct.model_code)
    if part_id:
        query = query.where(CatalogProduct.part_id == part_id)
    rows = db.scalars(query).all()
    if q:
        needle = q.strip()
        rows = [row for row in rows if needle in row.name or needle in row.brand or needle in row.model_code]
    return [product_dict(row) for row in rows]


@router.get("/api/products/placeholder.svg")
def placeholder(part: str = "ceiling", label: str = "示例"):
    return Response(example_svg(part, label or "示例", "示例图，非实拍"), media_type="image/svg+xml")


@router.get("/api/products/{product_id}/image.svg")
def product_image(product_id: str, db: Db):
    row = db.get(CatalogProduct, product_id)
    if row is None:
        raise HTTPException(status_code=404, detail="没有这件示例产品")
    return Response(example_svg(row.part_id, row.name, f"{row.brand} · {row.model_code}"), media_type="image/svg+xml")


@router.get("/api/admin/products")
def admin_products(db: Db, _: AdminDep, status: str | None = None, part_id: str | None = None):
    query = select(CatalogProduct).order_by(CatalogProduct.status, CatalogProduct.part_id, CatalogProduct.model_code)
    if status:
        query = query.where(CatalogProduct.status == status)
    if part_id:
        query = query.where(CatalogProduct.part_id == part_id)
    return [product_dict(row) for row in db.scalars(query).all()]


@router.post("/api/admin/products/import")
async def import_products(db: Db, _: AdminDep, file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件过大")
    try:
        parsed = parse_manual(file.filename or "upload", data)
    except ImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    created = []
    for row in parsed:
        existing = db.scalar(
            select(CatalogProduct).where(
                CatalogProduct.model_code == row["model_code"],
                CatalogProduct.part_id == row["part_id"],
                CatalogProduct.source.in_(["manual", "pack"]),
            )
        )
        if existing is None:
            existing = CatalogProduct(id=new_id("sku"), **row)
            db.add(existing)
        else:
            for key, value in row.items():
                setattr(existing, key, value)
            existing.status = "pending"
        created.append(existing)
    db.commit()
    for row in created:
        db.refresh(row)
    return {"imported": len(created), "status": "pending", "products": [product_dict(row) for row in created]}


@router.post("/api/admin/products/{product_id}/confirm")
def confirm_product(product_id: str, db: Db, _: AdminDep):
    row = db.get(CatalogProduct, product_id)
    if row is None:
        raise HTTPException(status_code=404, detail="没有这件产品")
    row.status = "confirmed"
    db.commit()
    db.refresh(row)
    return product_dict(row)


@router.get("/api/admin/samples/manual")
def sample_manual(_: AdminDep):
    path = SAMPLES / "示例手册.pdf"
    data = path.read_bytes() if path.is_file() else build_manual_pdf()
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename*=UTF-8''sample-manual.pdf"})


@router.get("/api/admin/samples/pack")
def sample_pack(_: AdminDep):
    path = SAMPLES / "示例图包.zip"
    data = path.read_bytes() if path.is_file() else build_image_zip()
    return Response(data, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=sample-pack.zip"})


class BindingIn(BaseModel):
    unit_type_id: str | None = None
    room_name: str = ""
    part_id: str
    product_id: str
    note: str = ""


@router.get("/api/projects/{project_id}/bindings")
def public_bindings(project_id: str, db: Db):
    rows = db.scalars(select(ProjectBinding).where(ProjectBinding.project_id == project_id)).all()
    return [binding_dict(row) for row in rows]


@router.post("/api/admin/projects/{project_id}/bindings")
def save_binding(project_id: str, body: BindingIn, db: Db, _: AdminDep):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    part = db.get(Part, body.part_id)
    product = db.get(CatalogProduct, body.product_id)
    if part is None or product is None or product.part_id != part.id or product.status != "confirmed":
        raise HTTPException(status_code=400, detail="请从已确认的同品类示例库里选")
    if body.unit_type_id:
        unit = db.get(UnitType, body.unit_type_id)
        if unit is None or unit.project_id != project.id:
            raise HTTPException(status_code=400, detail="户型不属于这个项目")
    room = (body.room_name or "").strip()[:40]
    existing = db.scalar(
        select(ProjectBinding).where(
            ProjectBinding.project_id == project.id,
            ProjectBinding.unit_type_id == body.unit_type_id,
            ProjectBinding.room_name == room,
            ProjectBinding.part_id == body.part_id,
        )
    )
    if existing is None:
        existing = ProjectBinding(
            id=new_id("bind"),
            project_id=project.id,
            unit_type_id=body.unit_type_id,
            room_name=room,
            part_id=body.part_id,
            product_id=product.id,
            note=body.note[:200],
        )
        db.add(existing)
    else:
        existing.product_id = product.id
        existing.note = body.note[:200]
    db.commit()
    db.refresh(existing)
    return binding_dict(existing)


@router.delete("/api/admin/projects/{project_id}/bindings/{binding_id}")
def delete_binding(project_id: str, binding_id: str, db: Db, _: AdminDep):
    row = db.get(ProjectBinding, binding_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="没有这条绑定")
    db.delete(row)
    db.commit()
    return {"ok": True}


class ModelJobIn(BaseModel):
    part_id: str
    name: str = Field(min_length=1, max_length=80)
    width_mm: int | None = None
    depth_mm: int | None = None
    height_mm: int | None = None
    image_names: list[str] = []


@router.post("/api/model-jobs")
def create_model_job(body: ModelJobIn, db: Db, _: AdminDep):
    part = db.get(Part, body.part_id)
    if part is None:
        raise HTTPException(status_code=400, detail="没有这个品类")
    width, depth, height = size_for(body.part_id, body.width_mm, body.depth_mm, body.height_mm)
    product = CatalogProduct(
        id=new_id("sku"),
        part_id=body.part_id,
        brand="通用件示例",
        model_code=f"GEN-{body.part_id[:2].upper()}",
        name=body.name,
        spec=f"通用件 {width}×{depth}×{height} mm",
        width_mm=width,
        depth_mm=depth,
        height_mm=height,
        domestic_price=0,
        import_price=0,
        status="confirmed",
        example=True,
        source="model_job",
        note="未接生模服务。已按尺寸用通用件入库，房间里按这个尺寸放置。",
    )
    db.add(product)
    job = WorkerJob(
        id=new_id("job"),
        kind="model_generate",
        status="fallback",
        payload={
            "part_id": body.part_id,
            "name": body.name,
            "width_mm": width,
            "depth_mm": depth,
            "height_mm": height,
            "image_names": body.image_names[:8],
        },
        result={"product_id": product.id, "mode": "generic_scale"},
    )
    db.add(job)
    db.commit()
    return {
        "id": job.id,
        "status": "fallback",
        "message": "未配置生模服务，没有发出付费请求。已按品类尺寸用通用件入库。",
        "product": product_dict(product),
    }


@router.get("/api/model-jobs/{job_id}")
def get_model_job(job_id: str, db: Db, _: AdminDep):
    job = db.get(WorkerJob, job_id)
    if job is None or job.kind != "model_generate":
        raise HTTPException(status_code=404, detail="没有这个生模任务")
    return {"id": job.id, "status": job.status, "payload": job.payload, "result": job.result}


@router.get("/api/admin/models")
def list_models(db: Db, _: AdminDep, project_id: str | None = None):
    query = select(LibraryModel).order_by(LibraryModel.created_at.desc())
    if project_id:
        query = query.where(LibraryModel.project_id == project_id)
    rows = db.scalars(query).all()
    return [
        {
            "id": row.id,
            "project_id": row.project_id,
            "filename": row.filename,
            "format": row.format,
            "note": row.note,
            "file_url": f"/api/models/{row.id}/file",
        }
        for row in rows
    ]


@router.post("/api/admin/models")
async def upload_model(
    db: Db,
    _: AdminDep,
    file: UploadFile = File(...),
    project_id: str = Form(""),
    note: str = Form(""),
):
    filename = file.filename or "model.glb"
    suffix = filename.rsplit(".", 1)[-1].lower()
    if suffix not in MODEL_FORMATS:
        raise HTTPException(status_code=400, detail="只接收 glTF、GLB、FBX、OBJ")
    data = await file.read()
    if not data or len(data) > 40 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件为空或过大")
    if project_id and db.get(Project, project_id) is None:
        raise HTTPException(status_code=400, detail="项目不存在")
    model_id = new_id("mdl")
    key = f"models/{model_id}.{suffix}"
    get_storage().put(key, data, file.content_type or "application/octet-stream")
    row = LibraryModel(
        id=model_id,
        project_id=project_id or None,
        filename=filename,
        format=suffix,
        storage_key=key,
        note=note[:200] or "上传的自制模型，可旋转；分开的网格可以换颜色。",
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "filename": row.filename, "format": row.format, "file_url": f"/api/models/{row.id}/file"}


@router.get("/api/models/{model_id}/file")
def model_file(model_id: str, db: Db):
    row = db.get(LibraryModel, model_id)
    if row is None:
        raise HTTPException(status_code=404, detail="没有这个模型")
    data, content_type = get_storage().get(row.storage_key)
    return Response(data, media_type=content_type, headers={"Content-Disposition": f'inline; filename="{row.filename}"'})
