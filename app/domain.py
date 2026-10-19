from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class ApplyOutcome(StrEnum):
    CREATED = "created"
    REPLACED = "replaced"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class NewTrade:
    trade_id: str
    version: int
    counterparty_id: str
    portfolio_id: str
    maturity_date: date
    created_date: date


@dataclass(frozen=True, slots=True)
class StoredTrade:
    trade_id: str
    version: int
    counterparty_id: str
    portfolio_id: str
    maturity_date: date
    created_date: date
    store_created_at: datetime
    store_updated_at: datetime
    expired: bool


@dataclass(frozen=True, slots=True)
class ItemResult:
    index: int
    trade_id: str | None
    outcome: str
    status_code: int
    trade: StoredTrade | None
    error_code: str | None
    error_message: str | None
    error_details: dict[str, object]
