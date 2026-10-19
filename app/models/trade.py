from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Index, Integer, String, false
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_trades_version_positive"),
        CheckConstraint("char_length(trade_id) > 0", name="ck_trades_trade_id_not_blank"),
        CheckConstraint(
            "char_length(counterparty_id) > 0",
            name="ck_trades_counterparty_id_not_blank",
        ),
        CheckConstraint("char_length(portfolio_id) > 0", name="ck_trades_portfolio_id_not_blank"),
        Index("ix_trades_expiry", "expired", "maturity_date"),
        Index("ix_trades_store_updated_at", "store_updated_at"),
    )

    trade_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    counterparty_id: Mapped[str] = mapped_column(String(64), nullable=False)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False)
    maturity_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_date: Mapped[date] = mapped_column(Date, nullable=False)
    store_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    store_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expired: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
