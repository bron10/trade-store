from datetime import date, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from tests.support import BUSINESS_INSTANT, new_trade

from app.clock import FixedClock
from app.errors import TradeNotFoundError, VersionConflictError
from app.models.trade import Trade
from app.services.trades import TradeService
from app.workers.expiry import run_expiry_once


def test_schema_version_is_applied(database) -> None:
    with database() as session:
        version = session.scalar(text("SELECT version_num FROM alembic_version"))
    assert version == "0002"


def test_persist_and_replace(database, clock: FixedClock) -> None:
    service = TradeService(clock, database, 100)
    outcome, created = service.ingest(new_trade())
    assert outcome.value == "created"
    assert created.expired is False
    assert created.store_created_at == clock.now()
    assert created.store_updated_at == clock.now()
    later = FixedClock(BUSINESS_INSTANT + timedelta(hours=1), "UTC")
    outcome, replaced = TradeService(later, database, 100).ingest(
        new_trade(version=2, counterparty_id="CP-9", created_date=date(1990, 1, 1))
    )
    assert outcome.value == "replaced"
    assert replaced.created_date == date(2026, 1, 15)
    assert replaced.counterparty_id == "CP-9"
    assert replaced.store_created_at == clock.now()
    assert replaced.store_updated_at == later.now()
    with pytest.raises(VersionConflictError):
        service.ingest(new_trade(version=1))
    assert service.get_trade("TRD-1").version == 2


def test_check_constraint_and_rollback(database, clock: FixedClock) -> None:
    with database() as session:
        with pytest.raises(IntegrityError):
            with session.begin():
                session.add(
                    Trade(
                        trade_id="BAD",
                        version=0,
                        counterparty_id="CP-1",
                        portfolio_id="PF-1",
                        maturity_date=date(2026, 12, 31),
                        created_date=date(2026, 1, 15),
                        store_created_at=clock.now(),
                        store_updated_at=clock.now(),
                        expired=False,
                    )
                )
    service = TradeService(clock, database, 100)
    with database() as session:
        with pytest.raises(IntegrityError):
            with session.begin():
                session.add(
                    Trade(
                        trade_id="GOOD",
                        version=1,
                        counterparty_id="CP-1",
                        portfolio_id="PF-1",
                        maturity_date=date(2026, 12, 31),
                        created_date=date(2026, 1, 15),
                        store_created_at=clock.now(),
                        store_updated_at=clock.now(),
                        expired=False,
                    )
                )
                session.flush()
                session.add(
                    Trade(
                        trade_id="ALSO-BAD",
                        version=0,
                        counterparty_id="CP-1",
                        portfolio_id="PF-1",
                        maturity_date=date(2026, 12, 31),
                        created_date=date(2026, 1, 15),
                        store_created_at=clock.now(),
                        store_updated_at=clock.now(),
                        expired=False,
                    )
                )
                session.flush()
    with pytest.raises(TradeNotFoundError):
        service.get_trade("GOOD")


def test_trigger_rejects_a_lower_version_update(database, clock: FixedClock) -> None:
    service = TradeService(clock, database, 100)
    service.ingest(new_trade(version=3))
    with database() as session:
        with pytest.raises(DBAPIError):
            with session.begin():
                session.execute(
                    text("UPDATE trades SET version = 2 WHERE trade_id = :trade_id"),
                    {"trade_id": "TRD-1"},
                )
    assert service.get_trade("TRD-1").version == 3


def test_expiry_is_idempotent_and_respects_the_boundary(database, clock: FixedClock) -> None:
    service = TradeService(clock, database, 100)
    service.ingest(new_trade(trade_id="DUE", maturity_date=date(2026, 10, 16)))
    service.ingest(new_trade(trade_id="STILL", maturity_date=date(2026, 10, 17)))
    later = FixedClock(BUSINESS_INSTANT + timedelta(days=1), "UTC")
    assert run_expiry_once(database, later) == 1
    due = service.get_trade("DUE")
    still = service.get_trade("STILL")
    assert due.expired is True
    assert due.store_created_at == clock.now()
    assert due.store_updated_at == later.now()
    assert still.expired is False
    assert still.store_created_at == clock.now()
    assert still.store_updated_at == clock.now()
    assert run_expiry_once(database, later) == 0
    assert service.get_trade("DUE").store_updated_at == due.store_updated_at

    revived = TradeService(later, database, 100)
    revived.ingest(new_trade(trade_id="DUE", version=2, maturity_date=date(2026, 10, 17)))
    current = revived.get_trade("DUE")
    assert current.expired is False
    assert current.created_date == date(2026, 1, 15)
    assert current.store_created_at == clock.now()
    assert current.store_updated_at == later.now()
