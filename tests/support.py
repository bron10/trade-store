from datetime import UTC, date, datetime

from app.domain import NewTrade

BUSINESS_INSTANT = datetime(2026, 10, 16, 15, 0, tzinfo=UTC)


def new_trade(**overrides: object) -> NewTrade:
    values: dict[str, object] = {
        "trade_id": "TRD-1",
        "version": 1,
        "counterparty_id": "CP-1",
        "portfolio_id": "PF-1",
        "maturity_date": date(2026, 12, 31),
        "created_date": date(2026, 1, 15),
    }
    values.update(overrides)
    return NewTrade(**values)  # type: ignore[arg-type]


def payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "trade_id": "TRD-1",
        "version": 1,
        "counterparty_id": "CP-1",
        "portfolio_id": "PF-1",
        "maturity_date": "2026-12-31",
        "created_date": "2026-01-15",
    }
    body.update(overrides)
    return body
