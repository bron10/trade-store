from datetime import date, datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.domain import ApplyOutcome, NewTrade, StoredTrade
from app.models.trade import Trade
from app.versioning import decide_version


def _require_aware(moment: datetime) -> None:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("store timestamps must be timezone-aware")


def _snapshot(row: Trade) -> StoredTrade:
    return StoredTrade(
        trade_id=row.trade_id,
        version=row.version,
        counterparty_id=row.counterparty_id,
        portfolio_id=row.portfolio_id,
        maturity_date=row.maturity_date,
        created_date=row.created_date,
        store_created_at=row.store_created_at,
        store_updated_at=row.store_updated_at,
        expired=row.expired,
    )


class TradeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def apply(
        self, trade: NewTrade, *, now: datetime, expired: bool
    ) -> tuple[ApplyOutcome, StoredTrade]:
        _require_aware(now)
        # Serialize writers for this trade id, including the first insert, so a
        # slower older version cannot pass the check before a newer version commits.
        self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:trade_id, 0))"),
            {"trade_id": trade.trade_id},
        )
        existing = self._session.scalar(
            select(Trade).where(Trade.trade_id == trade.trade_id).with_for_update()
        )
        stored_version = None if existing is None else existing.version
        decision = decide_version(stored_version, trade.version)
        if decision is ApplyOutcome.CONFLICT:
            assert existing is not None
            return decision, _snapshot(existing)
        if decision is ApplyOutcome.CREATED:
            row = Trade(
                trade_id=trade.trade_id,
                version=trade.version,
                counterparty_id=trade.counterparty_id,
                portfolio_id=trade.portfolio_id,
                maturity_date=trade.maturity_date,
                created_date=trade.created_date,
                store_created_at=now,
                store_updated_at=now,
                expired=expired,
            )
            self._session.add(row)
            self._session.flush()
            return decision, _snapshot(row)

        assert existing is not None
        existing.version = trade.version
        existing.counterparty_id = trade.counterparty_id
        existing.portfolio_id = trade.portfolio_id
        existing.maturity_date = trade.maturity_date
        existing.store_updated_at = now
        existing.expired = expired
        self._session.flush()
        return ApplyOutcome.REPLACED, _snapshot(existing)

    def get(self, trade_id: str) -> StoredTrade | None:
        row = self._session.get(Trade, trade_id)
        if row is None:
            return None
        return _snapshot(row)

    def list_trades(self, *, limit: int, offset: int) -> tuple[list[StoredTrade], int]:
        total_count = self._session.scalar(select(func.count()).select_from(Trade))
        rows = self._session.scalars(
            select(Trade)
            .order_by(Trade.store_updated_at.desc(), Trade.trade_id.asc())
            .limit(limit)
            .offset(offset)
        ).all()
        return [_snapshot(row) for row in rows], int(total_count or 0)

    def expire_due(self, *, business_today: date, now: datetime) -> int:
        _require_aware(now)
        result = self._session.execute(
            update(Trade)
            .where(Trade.expired.is_(False), Trade.maturity_date < business_today)
            .values(expired=True, store_updated_at=now)
            .returning(Trade.trade_id),
            execution_options={"synchronize_session": False},
        )
        return len(result.all())
