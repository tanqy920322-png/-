import json
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine = None
_session_factory = None


def get_engine():
    global _engine, _session_factory
    if _engine is not None:
        return _engine
    url = get_settings().database_url
    kwargs = {
        "pool_pre_ping": True,
        "json_serializer": lambda value: json.dumps(value, ensure_ascii=False),
    }
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_sqlite_fk(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    _engine = engine
    _session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine


def ensure_schema(engine) -> None:
    """Add columns introduced after the first scaffold without a migration tool."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    statements: list[str] = []
    if "parts" in tables:
        columns = {column["name"] for column in inspector.get_columns("parts")}
        if "pricing_mode" not in columns:
            statements.append("ALTER TABLE parts ADD COLUMN pricing_mode VARCHAR(16) DEFAULT 'area'")
        if "allows_brand_tier" not in columns:
            statements.append("ALTER TABLE parts ADD COLUMN allows_brand_tier BOOLEAN DEFAULT FALSE")
        if "visual" not in columns:
            statements.append("ALTER TABLE parts ADD COLUMN visual BOOLEAN DEFAULT FALSE")
    if statements or ("schemes" in tables and engine.dialect.name == "postgresql"):
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
            if "schemes" in tables and engine.dialect.name == "postgresql":
                connection.execute(text("ALTER TABLE schemes ALTER COLUMN style_id DROP NOT NULL"))


def get_session_factory():
    get_engine()
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
