import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.clock import Clock, SystemClock
from app.config import get_settings
from app.db.session import make_engine, make_session_factory
from app.logging import configure_logging
from app.repositories.trades import TradeRepository

logger = logging.getLogger(__name__)


def run_expiry_once(session_factory: sessionmaker[Session], clock: Clock) -> int:
    with session_factory() as session, session.begin():
        return TradeRepository(session).expire_due(
            business_today=clock.business_today(),
            now=clock.now(),
        )


def wait_for_schema(engine: Engine, timeout_seconds: int = 60) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "unknown"
    while time.monotonic() < deadline:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT trade_id FROM trades LIMIT 0"))
            return
        except Exception as exc:
            last_error = type(exc).__name__
            time.sleep(1)
    raise TimeoutError(f"database schema was not ready ({last_error})")


def touch_heartbeat(path: str) -> None:
    heartbeat = Path(path)
    heartbeat.parent.mkdir(parents=True, exist_ok=True)
    heartbeat.write_text(datetime.now(UTC).isoformat(), encoding="utf-8")


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)
    wait_for_schema(engine)
    session_factory = make_session_factory(engine)
    clock = SystemClock(settings.business_timezone)
    logger.info(
        "expiry worker started interval=%s timezone=%s",
        settings.expiry_interval_seconds,
        settings.business_timezone,
    )
    try:
        while True:
            try:
                updated = run_expiry_once(session_factory, clock)
                logger.info("expiry run complete updated=%s", updated)
                touch_heartbeat(settings.expiry_heartbeat_path)
            except Exception as exc:
                logger.error("expiry run failed: %s", type(exc).__name__)
            time.sleep(settings.expiry_interval_seconds)
    except KeyboardInterrupt:
        logger.info("expiry worker stopped")


if __name__ == "__main__":
    main()
