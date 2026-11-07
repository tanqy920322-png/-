import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.database import ensure_schema, get_engine, get_session_factory
from app.models import Base
from app.routers import admin, ai, assets, auth, catalog, exports, selections
from app.seed import seed
from app.services.queue import probe_redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_schema(engine)
    if settings.auto_seed:
        db = get_session_factory()()
        try:
            seed(db)
        finally:
            db.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="精装选配 API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(catalog.router)
    app.include_router(selections.router)
    app.include_router(admin.router)
    app.include_router(assets.router)
    app.include_router(exports.router)
    app.include_router(ai.router)

    @app.get("/api/health")
    @app.get("/health")
    def health():
        db_status = "down"
        db = get_session_factory()()
        try:
            db.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception:
            db_status = "down"
        finally:
            db.close()
        return {
            "ok": db_status == "ok",
            "db": db_status,
            "redis": probe_redis(get_settings().redis_url),
        }

    @app.get("/")
    def root():
        return {"service": "fitout-selection", "docs": "/docs", "health": "/api/health"}

    return app


app = create_app()
