"""Create the trades table and the lower-version guard."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FUNCTION = """
CREATE OR REPLACE FUNCTION trades_reject_lower_version()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.version < OLD.version THEN
        RAISE EXCEPTION 'version_conflict'
            USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$$;
"""

_TRIGGER = """
CREATE TRIGGER trades_version_monotonic
BEFORE UPDATE ON trades
FOR EACH ROW
EXECUTE FUNCTION trades_reject_lower_version();
"""


def upgrade() -> None:
    op.create_table(
        "trades",
        sa.Column("trade_id", sa.String(length=64), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("counterparty_id", sa.String(length=64), nullable=False),
        sa.Column("portfolio_id", sa.String(length=64), nullable=False),
        sa.Column("maturity_date", sa.Date(), nullable=False),
        sa.Column("created_date", sa.Date(), nullable=False),
        sa.Column("updated_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expired", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("version >= 1", name="ck_trades_version_positive"),
        sa.CheckConstraint("char_length(trade_id) > 0", name="ck_trades_trade_id_not_blank"),
        sa.CheckConstraint(
            "char_length(counterparty_id) > 0",
            name="ck_trades_counterparty_id_not_blank",
        ),
        sa.CheckConstraint(
            "char_length(portfolio_id) > 0",
            name="ck_trades_portfolio_id_not_blank",
        ),
    )
    op.create_index("ix_trades_expiry", "trades", ["expired", "maturity_date"])
    op.create_index("ix_trades_updated_date", "trades", ["updated_date"])
    op.execute(_FUNCTION)
    op.execute(_TRIGGER)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trades_version_monotonic ON trades")
    op.execute("DROP FUNCTION IF EXISTS trades_reject_lower_version()")
    op.drop_index("ix_trades_expiry", table_name="trades")
    op.drop_index("ix_trades_updated_date", table_name="trades")
    op.drop_table("trades")
