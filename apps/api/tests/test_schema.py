from sqlalchemy import create_engine, text

from app.database import ensure_schema


def test_sqlite_rebuild_allows_schemes_without_style(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE styles (id VARCHAR(40) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE parts (id VARCHAR(32) PRIMARY KEY)"))
        connection.execute(text("INSERT INTO parts (id) VALUES ('sanitary')"))
        connection.execute(text("INSERT INTO styles (id) VALUES ('cream')"))
        connection.execute(
            text(
                """
                CREATE TABLE schemes (
                    id VARCHAR(80) NOT NULL PRIMARY KEY,
                    style_id VARCHAR(40) NOT NULL,
                    part_id VARCHAR(32) NOT NULL,
                    scheme_index INTEGER NOT NULL,
                    name VARCHAR(80) NOT NULL,
                    summary TEXT,
                    unit_price NUMERIC(12, 2) NOT NULL,
                    is_default BOOLEAN,
                    material JSON,
                    FOREIGN KEY(style_id) REFERENCES styles (id),
                    FOREIGN KEY(part_id) REFERENCES parts (id)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO schemes (
                    id, style_id, part_id, scheme_index, name, summary, unit_price, is_default, material
                ) VALUES ('cream-ceiling-1', 'cream', 'sanitary', 1, '旧方案', '', 1, 1, '{}')
                """
            )
        )

    ensure_schema(engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO schemes (
                    id, style_id, part_id, scheme_index, name, summary, unit_price, is_default, material
                ) VALUES ('sanitary-1', NULL, 'sanitary', 1, '龙头花洒组', '', 1680, 1, '{}')
                """
            )
        )
        kept = connection.execute(text("SELECT style_id FROM schemes WHERE id = 'cream-ceiling-1'")).scalar_one()
        shared = connection.execute(text("SELECT style_id FROM schemes WHERE id = 'sanitary-1'")).scalar_one()
    assert kept == "cream"
    assert shared is None
