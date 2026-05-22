from sqlalchemy import create_engine, inspect, text

from app import database as database_module


def test_legacy_users_table_allows_password_users_after_migration(tmp_path, monkeypatch):
    """旧卡密表的 card_key/access_link NOT NULL 约束必须在迁移后放开。"""
    db_path = tmp_path / "legacy.db"
    legacy_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    with legacy_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER NOT NULL PRIMARY KEY,
                card_key VARCHAR(255) NOT NULL,
                access_link VARCHAR(255) NOT NULL,
                is_active BOOLEAN,
                created_at DATETIME,
                last_used DATETIME,
                usage_limit INTEGER,
                usage_count INTEGER,
                username VARCHAR(255),
                password_hash VARCHAR(255),
                display_name VARCHAR(255)
            )
        """))
        conn.execute(
            text("""
                INSERT INTO users (
                    id, card_key, access_link, is_active, usage_limit, usage_count
                ) VALUES (
                    1, 'LEGACY-CARD', 'http://localhost:9800/access/LEGACY-CARD', 1, 3, 1
                )
            """)
        )

    monkeypatch.setattr(database_module, "engine", legacy_engine)

    database_module._migrate_database_schema()

    columns = {column["name"]: column for column in inspect(legacy_engine).get_columns("users")}
    assert columns["card_key"]["nullable"] is True
    assert columns["access_link"]["nullable"] is True

    with legacy_engine.begin() as conn:
        legacy_user = conn.execute(
            text("SELECT card_key, access_link, usage_limit, usage_count FROM users WHERE id = 1")
        ).mappings().one()
        assert legacy_user["card_key"] == "LEGACY-CARD"
        assert legacy_user["usage_limit"] == 3
        assert legacy_user["usage_count"] == 1

        conn.execute(
            text("""
                INSERT INTO users (
                    username, password_hash, is_active, usage_limit, usage_count
                ) VALUES (
                    'new-user', 'hash', 1, 0, 0
                )
            """)
        )

        created = conn.execute(
            text("SELECT username, card_key, access_link FROM users WHERE username = 'new-user'")
        ).mappings().one()
        assert created["card_key"] is None
        assert created["access_link"] is None
