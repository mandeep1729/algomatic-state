"""Create strategy_probe_trades table for detailed per-trade records.

Stores individual trades from probe runs with entry/exit justifications,
linked back to the aggregated strategy_probe_results via FK.

Revision ID: 016
Revises: 015
Create Date: 2026-02-08
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_probe_trades",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "strategy_probe_result_id", sa.BigInteger,
            sa.ForeignKey("strategy_probe_results.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("open_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(5), nullable=False),
        sa.Column("open_justification", sa.Text, nullable=True),
        sa.Column("close_justification", sa.Text, nullable=True),
        sa.Column("pnl", sa.Float, nullable=False),
        sa.Column("pnl_pct", sa.Float, nullable=False),
        sa.Column("bars_held", sa.Integer, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index(
        "ix_probe_trades_result_id", "strategy_probe_trades",
        ["strategy_probe_result_id"],
    )
    op.create_index("ix_probe_trades_ticker", "strategy_probe_trades", ["ticker"])
    op.create_index("ix_probe_trades_direction", "strategy_probe_trades", ["direction"])
    op.create_index("ix_probe_trades_open_ts", "strategy_probe_trades", ["open_timestamp"])


def downgrade() -> None:
    op.drop_table("strategy_probe_trades")
