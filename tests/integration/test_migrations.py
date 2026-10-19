import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.db.session import make_engine


def test_alembic_upgrade_and_downgrade_from_a_clean_database(engine) -> None:
    del engine
    previous = os.environ["DATABASE_URL"]
    name = "trade_store_migration_test"
    admin = create_engine(
        previous.rsplit("/", 1)[0] + "/postgres",
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    migration_url = previous.rsplit("/", 1)[0] + f"/{name}"
    config = Config("alembic.ini")
    try:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        os.environ["DATABASE_URL"] = migration_url
        get_settings.cache_clear()
        command.upgrade(config, "head")
        migrated = make_engine(migration_url)
        try:
            assert "trades" in inspect(migrated).get_table_names()
            with migrated.connect() as connection:
                trigger = connection.execute(
                    text("SELECT 1 FROM pg_trigger WHERE tgname = 'trades_version_monotonic'")
                ).scalar()
                version = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar()
            assert trigger == 1
            assert version == "0002"
        finally:
            migrated.dispose()
        assert os.environ["DATABASE_URL"].endswith(name)
        command.downgrade(config, "base")
        downgraded = make_engine(migration_url)
        try:
            assert "trades" not in inspect(downgraded).get_table_names()
        finally:
            downgraded.dispose()
        command.upgrade(config, "head")
    finally:
        os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()
