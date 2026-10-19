"""Rename updated_date and record when the store first accepted the trade."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("trades", "updated_date", new_column_name="store_updated_at")
    op.drop_index("ix_trades_updated_date", table_name="trades")
    op.create_index("ix_trades_store_updated_at", "trades", ["store_updated_at"])
    op.add_column(
        "trades",
        sa.Column("store_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE trades SET store_created_at = store_updated_at")
    op.alter_column("trades", "store_created_at", nullable=False)


def downgrade() -> None:
    op.drop_column("trades", "store_created_at")
    op.drop_index("ix_trades_store_updated_at", table_name="trades")
    op.create_index("ix_trades_updated_date", "trades", ["store_updated_at"])
    op.alter_column("trades", "store_updated_at", new_column_name="updated_date")
