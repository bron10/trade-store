import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://trade:trade@127.0.0.1:5432/trade_store_test",
)
os.environ.setdefault("BUSINESS_TIMEZONE", "UTC")
os.environ.setdefault("LOG_LEVEL", "WARNING")

import re  # noqa: E402
import time  # noqa: E402
from collections.abc import Iterator  # noqa: E402

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool
from tests.support import BUSINESS_INSTANT

from app.clock import FixedClock
from app.config import get_settings
from app.db.session import make_engine, make_session_factory
from app.main import create_app


def wait_until_postgres(url: str, timeout_seconds: int = 60) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "unknown"
    admin_url = make_url(url).set(database="postgres")
    while time.monotonic() < deadline:
        engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except Exception as exc:
            last_error = type(exc).__name__
            time.sleep(1)
        finally:
            engine.dispose()
    raise TimeoutError(f"PostgreSQL did not become ready ({last_error})")


def ensure_test_database(url: str) -> None:
    parsed = make_url(url)
    database_name = parsed.database
    if database_name is None or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database_name):
        raise RuntimeError("Refusing to create a database with an unsafe name.")
    admin = create_engine(
        parsed.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    try:
        with admin.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": database_name},
            ).scalar()
            if exists is None:
                connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    finally:
        admin.dispose()


def upgrade_to_head() -> None:
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = os.environ["DATABASE_URL"]
    wait_until_postgres(url)
    ensure_test_database(url)
    upgrade_to_head()
    db_engine = make_engine(url)
    yield db_engine
    db_engine.dispose()


@pytest.fixture(scope="session")
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return make_session_factory(engine)


@pytest.fixture(scope="session")
def clock() -> FixedClock:
    return FixedClock(BUSINESS_INSTANT, "UTC")


@pytest.fixture(scope="session")
def app(engine: Engine, session_factory: sessionmaker[Session], clock: FixedClock):
    application = create_app()
    extra_engine = application.state.engine
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.state.clock = clock
    extra_engine.dispose()
    return application


@pytest.fixture
def database(session_factory: sessionmaker[Session]) -> Iterator[sessionmaker[Session]]:
    _truncate(session_factory)
    yield session_factory
    _truncate(session_factory)


@pytest.fixture
def client(app, database: sessionmaker[Session]) -> Iterator[TestClient]:
    del database
    with TestClient(app) as test_client:
        yield test_client


def _truncate(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session, session.begin():
        session.execute(text("TRUNCATE TABLE trades"))
