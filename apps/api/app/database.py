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


def _scheme_style_is_required(inspector, tables: set[str]) -> bool:
    if "schemes" not in tables:
        return False
    for column in inspector.get_columns("schemes"):
        if column["name"] == "style_id":
            return not column.get("nullable", True)
    return False


def _relax_sqlite_scheme_style(connection) -> None:
    """SQLite cannot DROP NOT NULL. Rebuild schemes so shared SKUs can omit style_id."""
    from sqlalchemy import text

    connection.execute(text("PRAGMA foreign_keys=OFF"))
    connection.execute(text("DROP TABLE IF EXISTS schemes_new"))
    connection.execute(
        text(
            """
            CREATE TABLE schemes_new (
                id VARCHAR(80) NOT NULL PRIMARY KEY,
                style_id VARCHAR(40),
                part_id VARCHAR(32) NOT NULL,
                scheme_index INTEGER NOT NULL,
                name VARCHAR(80) NOT NULL,
                summary TEXT,
                unit_price NUMERIC(12, 2) NOT NULL,
                is_default BOOLEAN,
                material JSON,
                CONSTRAINT uq_scheme_slot UNIQUE (style_id, part_id, scheme_index),
                FOREIGN KEY(style_id) REFERENCES styles (id),
                FOREIGN KEY(part_id) REFERENCES parts (id)
            )
            """
        )
    )
    connection.execute(
        text(
            """
            INSERT INTO schemes_new (
                id, style_id, part_id, scheme_index, name, summary, unit_price, is_default, material
            )
            SELECT id, style_id, part_id, scheme_index, name, summary, unit_price, is_default, material
            FROM schemes
            """
        )
    )
    connection.execute(text("DROP TABLE schemes"))
    connection.execute(text("ALTER TABLE schemes_new RENAME TO schemes"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_schemes_style_id ON schemes (style_id)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_schemes_part_id ON schemes (part_id)"))
    connection.execute(text("PRAGMA foreign_keys=ON"))


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
    if "scheme_items" in tables:
        item_columns = {column["name"] for column in inspector.get_columns("scheme_items")}
        if "room_name" not in item_columns:
            statements.append("ALTER TABLE scheme_items ADD COLUMN room_name VARCHAR(40) DEFAULT ''")
        if "group_label" not in item_columns:
            statements.append("ALTER TABLE scheme_items ADD COLUMN group_label VARCHAR(80) DEFAULT ''")
        if "display_part_id" not in item_columns:
            statements.append("ALTER TABLE scheme_items ADD COLUMN display_part_id VARCHAR(32)")
    relax_sqlite = engine.dialect.name == "sqlite" and _scheme_style_is_required(inspector, tables)
    relax_postgres = engine.dialect.name == "postgresql" and _scheme_style_is_required(inspector, tables)
    if statements or relax_sqlite or relax_postgres:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
            if relax_postgres:
                connection.execute(text("ALTER TABLE schemes ALTER COLUMN style_id DROP NOT NULL"))
            if relax_sqlite:
                _relax_sqlite_scheme_style(connection)


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
