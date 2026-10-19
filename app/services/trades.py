import logging
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.clock import Clock
from app.db.pg import is_unique_violation, is_version_conflict
from app.domain import ApplyOutcome, ItemResult, NewTrade, StoredTrade
from app.errors import (
    InternalError,
    InvalidBatchError,
    MaturityDateError,
    TradeNotFoundError,
    VersionConflictError,
    validation_details,
)
from app.repositories.trades import TradeRepository
from app.schemas.trade import TradeCreate

logger = logging.getLogger(__name__)

_INTERNAL_MESSAGE = "The trade could not be stored."


class TradeService:
    def __init__(
        self,
        clock: Clock,
        session_factory: sessionmaker[Session],
        bulk_max_items: int,
    ) -> None:
        self._clock = clock
        self._session_factory = session_factory
        self._bulk_max_items = bulk_max_items

    def ingest(self, trade: NewTrade) -> tuple[ApplyOutcome, StoredTrade]:
        self._check_maturity(trade)
        try:
            return self._apply_once(trade)
        except SQLAlchemyError as exc:
            if is_version_conflict(exc):
                raise self._conflict(trade) from exc
            if not is_unique_violation(exc):
                logger.error("trade ingestion failed type=%s", type(exc).__name__)
                raise InternalError() from None
        try:
            return self._apply_once(trade)
        except SQLAlchemyError as exc:
            if is_version_conflict(exc):
                raise self._conflict(trade) from exc
            logger.error("trade ingestion failed type=%s", type(exc).__name__)
            raise InternalError() from None

    def _conflict(self, trade: NewTrade) -> VersionConflictError:
        stored_version = trade.version
        with self._session_factory() as session:
            found = TradeRepository(session).get(trade.trade_id)
        if found is not None:
            stored_version = found.version
        return VersionConflictError(trade.trade_id, trade.version, stored_version)

    def ingest_many(self, raw_items: list[Any]) -> list[ItemResult]:
        if len(raw_items) > self._bulk_max_items:
            raise InvalidBatchError(
                f"Bulk request exceeds the maximum of {self._bulk_max_items} trades.",
                details={"max_items": self._bulk_max_items, "received": len(raw_items)},
            )
        return [self._ingest_raw(index, raw) for index, raw in enumerate(raw_items)]

    def get_trade(self, trade_id: str) -> StoredTrade:
        with self._session_factory() as session:
            found = TradeRepository(session).get(trade_id)
        if found is None:
            raise TradeNotFoundError(trade_id)
        return found

    def list_trades(self, *, limit: int, offset: int) -> tuple[list[StoredTrade], int]:
        with self._session_factory() as session:
            return TradeRepository(session).list_trades(limit=limit, offset=offset)

    def _apply_once(self, trade: NewTrade) -> tuple[ApplyOutcome, StoredTrade]:
        with self._session_factory() as session, session.begin():
            outcome, stored = TradeRepository(session).apply(
                trade,
                now=self._clock.now(),
                expired=False,
            )
            if outcome is ApplyOutcome.CONFLICT:
                raise VersionConflictError(trade.trade_id, trade.version, stored.version)
            return outcome, stored

    def _check_maturity(self, trade: NewTrade) -> None:
        business_date = self._clock.business_today()
        if trade.maturity_date < business_date:
            raise MaturityDateError(
                trade_id=trade.trade_id,
                maturity_date=trade.maturity_date,
                business_date=business_date,
                business_timezone=self._clock.timezone_name,
            )

    def _ingest_raw(self, index: int, raw: Any) -> ItemResult:
        trade_id = (
            raw.get("trade_id")
            if isinstance(raw, dict) and isinstance(raw.get("trade_id"), str)
            else None
        )
        if not isinstance(raw, dict):
            return _rejected(
                index,
                trade_id,
                422,
                "validation_error",
                "Each trade must be an object.",
                {
                    "errors": [
                        {"loc": [], "msg": "Each trade must be an object.", "type": "dict_type"}
                    ]
                },
            )
        try:
            trade = TradeCreate.model_validate(raw).to_domain()
        except ValidationError as exc:
            return _rejected(
                index,
                trade_id,
                422,
                "validation_error",
                "Trade validation failed.",
                validation_details(exc.errors()),
            )
        try:
            outcome, stored = self.ingest(trade)
        except MaturityDateError as exc:
            return _rejected(
                index, trade.trade_id, exc.status_code, exc.code, exc.message, exc.details
            )
        except VersionConflictError as exc:
            return _rejected(
                index, trade.trade_id, exc.status_code, exc.code, exc.message, exc.details
            )
        except SQLAlchemyError as exc:
            if is_version_conflict(exc):
                return _rejected(
                    index,
                    trade.trade_id,
                    409,
                    "version_conflict",
                    "Incoming version is lower than the stored version.",
                    {"trade_id": trade.trade_id, "incoming_version": trade.version},
                )
            logger.error("bulk item database failure index=%s type=%s", index, type(exc).__name__)
            return _rejected(index, trade.trade_id, 500, "internal_error", _INTERNAL_MESSAGE, {})
        except Exception as exc:
            logger.error("bulk item failed index=%s type=%s", index, type(exc).__name__)
            return _rejected(index, trade.trade_id, 500, "internal_error", _INTERNAL_MESSAGE, {})
        status_code = 201 if outcome is ApplyOutcome.CREATED else 200
        return ItemResult(
            index=index,
            trade_id=stored.trade_id,
            outcome=outcome.value,
            status_code=status_code,
            trade=stored,
            error_code=None,
            error_message=None,
            error_details={},
        )


def _rejected(
    index: int,
    trade_id: str | None,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, object],
) -> ItemResult:
    return ItemResult(
        index=index,
        trade_id=trade_id,
        outcome="rejected",
        status_code=status_code,
        trade=None,
        error_code=code,
        error_message=message,
        error_details=details,
    )
