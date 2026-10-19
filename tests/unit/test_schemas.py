from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError
from tests.support import payload

from app.schemas.trade import TradeCreate


def test_valid_trade_is_accepted() -> None:
    trade = TradeCreate.model_validate(payload())
    assert trade.maturity_date == date(2026, 12, 31)
    assert trade.version == 1


def test_required_fields_are_enforced() -> None:
    body = payload()
    del body["portfolio_id"]
    with pytest.raises(ValidationError):
        TradeCreate.model_validate(body)


def test_version_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        TradeCreate.model_validate(payload(version=0))
    with pytest.raises(ValidationError):
        TradeCreate.model_validate(payload(version=-1))


def test_fractional_and_boolean_versions_are_rejected() -> None:
    with pytest.raises(ValidationError):
        TradeCreate.model_validate(payload(version=1.5))
    with pytest.raises(ValidationError):
        TradeCreate.model_validate(payload(version=True))


def test_client_cannot_supply_server_fields() -> None:
    with pytest.raises(ValidationError):
        TradeCreate.model_validate(payload(expired=False))
    with pytest.raises(ValidationError):
        TradeCreate.model_validate(
            payload(store_updated_at=datetime(2026, 10, 16, tzinfo=UTC).isoformat())
        )
    with pytest.raises(ValidationError):
        TradeCreate.model_validate(
            payload(store_created_at=datetime(2026, 10, 16, tzinfo=UTC).isoformat())
        )


def test_blank_and_unsafe_identifiers_are_rejected() -> None:
    with pytest.raises(ValidationError):
        TradeCreate.model_validate(payload(trade_id=""))
    with pytest.raises(ValidationError):
        TradeCreate.model_validate(payload(counterparty_id="has space"))
    with pytest.raises(ValidationError):
        TradeCreate.model_validate(payload(portfolio_id="../pf"))


def test_date_only_values_are_required() -> None:
    with pytest.raises(ValidationError):
        TradeCreate.model_validate(payload(maturity_date="2026-12-31T00:00:00"))
    with pytest.raises(ValidationError):
        TradeCreate.model_validate(payload(created_date="not-a-date"))
