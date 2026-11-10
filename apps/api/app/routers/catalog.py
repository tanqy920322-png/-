from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.constants import ASSET_KINDS, PROCUREMENT_CATEGORIES
from app.deps import Db
from app.models import Part, Project, Style
from app.services.serialize import project_dict, style_dict

router = APIRouter(tags=["catalog"])


@router.get("/api/meta")
def meta():
    return {
        "procurement_categories": [{"id": key, "name": label} for key, label in PROCUREMENT_CATEGORIES],
        "asset_kinds": [{"id": key, "name": label} for key, label in ASSET_KINDS],
        "selection_statuses": [
            {"id": "draft", "name": "选配中"},
            {"id": "submitted", "name": "已提交"},
        ],
    }


@router.get("/api/parts")
def list_parts(db: Db):
    rows = db.scalars(select(Part).order_by(Part.sort_order, Part.id)).all()
    return [
        {
            "id": part.id,
            "name": part.name,
            "sort_order": part.sort_order,
            "pricing": part.pricing_mode,
            "visual": bool(part.visual),
            "allows_brand_tier": bool(part.allows_brand_tier),
        }
        for part in rows
    ]


@router.get("/api/projects")
def list_projects(db: Db):
    rows = db.scalars(select(Project).where(Project.status == "published").order_by(Project.code)).all()
    return [project_dict(db, project) for project in rows]


@router.get("/api/projects/{code}")
def get_project(code: str, db: Db):
    project = db.scalar(select(Project).where(Project.code == code.strip().upper()))
    if project is None or project.status != "published":
        raise HTTPException(status_code=404, detail="项目不存在或尚未发布")
    return project_dict(db, project)


@router.get("/api/styles")
def list_styles(db: Db):
    styles = db.scalars(select(Style).order_by(Style.sort_order, Style.id)).all()
    return [style_dict(db, style) for style in styles]
