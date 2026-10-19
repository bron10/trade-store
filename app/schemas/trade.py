import re
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.domain import ItemResult, NewTrade, StoredTrade

IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$"
_CALENDAR_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _reject_bool(value: object) -> object:
    if isinstance(value, bool):
        raise ValueError("version must be an integer")
    return value


def _calendar_date(value: object) -> object:
    if isinstance(value, datetime):
        raise ValueError("expected a calendar date")
    if isinstance(value, str) and _CALENDAR_DATE.fullmatch(value) is None:
        raise ValueError("expected a calendar date in YYYY-MM-DD form")
    return value


Version = Annotated[int, BeforeValidator(_reject_bool)]
CalendarDate = Annotated[date, BeforeValidator(_calendar_date)]


class TradeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_id: str = Field(pattern=IDENTIFIER_PATTERN)
    version: Version = Field(gt=0, le=2_147_483_647)
    counterparty_id: str = Field(pattern=IDENTIFIER_PATTERN)
    portfolio_id: str = Field(pattern=IDENTIFIER_PATTERN)
    maturity_date: CalendarDate
    created_date: CalendarDate

    def to_domain(self) -> NewTrade:
        return NewTrade(
            trade_id=self.trade_id,
            version=self.version,
            counterparty_id=self.counterparty_id,
            portfolio_id=self.portfolio_id,
            maturity_date=self.maturity_date,
            created_date=self.created_date,
        )


class TradeRead(BaseModel):
    trade_id: str
    version: int
    counterparty_id: str
    portfolio_id: str
    maturity_date: date
    created_date: date
    store_created_at: datetime
    store_updated_at: datetime
    expired: bool

    @classmethod
    def from_stored(cls, trade: StoredTrade) -> "TradeRead":
        return cls(
            trade_id=trade.trade_id,
            version=trade.version,
            counterparty_id=trade.counterparty_id,
            portfolio_id=trade.portfolio_id,
            maturity_date=trade.maturity_date,
            created_date=trade.created_date,
            store_created_at=trade.store_created_at,
            store_updated_at=trade.store_updated_at,
            expired=trade.expired,
        )


class TradePage(BaseModel):
    items: list[TradeRead]
    limit: int
    offset: int
    total: int


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


class BulkItemError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class BulkItemResult(BaseModel):
    index: int
    trade_id: str | None
    outcome: str
    status_code: int
    trade: TradeRead | None = None
    error: BulkItemError | None = None

    @classmethod
    def from_item(cls, item: ItemResult) -> "BulkItemResult":
        error = None
        if item.error_code is not None:
            error = BulkItemError(
                code=item.error_code,
                message=item.error_message or "Request failed.",
                details=item.error_details,
            )
        return cls(
            index=item.index,
            trade_id=item.trade_id,
            outcome=item.outcome,
            status_code=item.status_code,
            trade=None if item.trade is None else TradeRead.from_stored(item.trade),
            error=error,
        )


class BulkResponse(BaseModel):
    results: list[BulkItemResult]


class BulkRequest(BaseModel):
    """Envelope for bulk ingestion.

    Items are untyped here so one invalid trade does not reject the whole batch.
    Each element is validated individually.
    """

    model_config = ConfigDict(extra="forbid")

    trades: list[Any] = Field(min_length=1)
