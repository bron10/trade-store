from datetime import date

import pytest
from tests.support import BUSINESS_INSTANT, new_trade, payload

from app.clock import FixedClock
from app.domain import ApplyOutcome, StoredTrade
from app.errors import InvalidBatchError, MaturityDateError
from app.repositories.trades import TradeRepository
from app.services.trades import TradeService


class FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def begin(self):
        return self


def _factory() -> FakeSession:
    return FakeSession()


def _stored(trade_id: str = "TRD-1", version: int = 1) -> StoredTrade:
    return StoredTrade(
        trade_id=trade_id,
        version=version,
        counterparty_id="CP-1",
        portfolio_id="PF-1",
        maturity_date=date(2026, 12, 31),
        created_date=date(2026, 1, 15),
        store_created_at=BUSINESS_INSTANT,
        store_updated_at=BUSINESS_INSTANT,
        expired=False,
    )


def test_past_maturity_does_not_touch_the_database(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(self, trade, *, now, expired):
        raise AssertionError("database should not be used")

    monkeypatch.setattr(TradeRepository, "apply", explode)
    service = TradeService(FixedClock(BUSINESS_INSTANT, "UTC"), _factory, 10)
    with pytest.raises(MaturityDateError) as caught:
        service.ingest(new_trade(maturity_date=date(2026, 10, 15)))
    assert caught.value.details["business_date"] == "2026-10-16"
    assert caught.value.details["maturity_date"] == "2026-10-15"


def test_maturity_on_the_business_date_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_apply(self, trade, *, now, expired):
        seen["expired"] = expired
        seen["now"] = now
        return ApplyOutcome.CREATED, _stored(trade.trade_id, trade.version)

    monkeypatch.setattr(TradeRepository, "apply", fake_apply)
    service = TradeService(FixedClock(BUSINESS_INSTANT, "UTC"), _factory, 10)
    outcome, stored = service.ingest(new_trade(maturity_date=date(2026, 10, 16)))
    assert outcome is ApplyOutcome.CREATED
    assert stored.trade_id == "TRD-1"
    assert seen["expired"] is False
    assert seen["now"] == BUSINESS_INSTANT


def test_bulk_keeps_order_and_continues_after_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    applied: list[str] = []

    def fake_apply(self, trade, *, now, expired):
        applied.append(trade.trade_id)
        assert expired is False
        assert now.tzinfo is not None
        if trade.trade_id == "T-conflict":
            return ApplyOutcome.CONFLICT, _stored("T-conflict", version=5)
        return ApplyOutcome.CREATED, _stored(trade.trade_id, trade.version)

    monkeypatch.setattr(TradeRepository, "apply", fake_apply)
    service = TradeService(FixedClock(BUSINESS_INSTANT, "UTC"), _factory, 10)
    results = service.ingest_many(
        [
            "not-an-object",
            payload(trade_id="T-invalid", version=0),
            payload(trade_id="T-past", maturity_date="2026-10-15"),
            payload(trade_id="T-ok"),
            payload(trade_id="T-conflict", version=1),
        ]
    )
    assert [item.index for item in results] == [0, 1, 2, 3, 4]
    assert results[0].trade_id is None
    assert results[0].status_code == 422
    assert results[1].trade_id == "T-invalid"
    assert results[1].error_code == "validation_error"
    assert results[2].error_code == "maturity_in_past"
    assert results[3].outcome == "created"
    assert results[3].status_code == 201
    assert results[4].status_code == 409
    assert results[4].error_code == "version_conflict"
    assert applied == ["T-ok", "T-conflict"]


def test_bulk_over_the_limit_is_rejected_before_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(self, trade, *, now, expired):
        raise AssertionError("database should not be used")

    monkeypatch.setattr(TradeRepository, "apply", explode)
    service = TradeService(FixedClock(BUSINESS_INSTANT, "UTC"), _factory, 1)
    with pytest.raises(InvalidBatchError) as caught:
        service.ingest_many([payload(trade_id="A"), payload(trade_id="B")])
    assert caught.value.details == {"max_items": 1, "received": 2}
