"""Create probe_strategies and strategy_probe_results tables.

Strategy catalog and aggregated probe result storage for the
100-strategy probe system.

Revision ID: 015
Revises: 014
Create Date: 2026-02-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Strategy catalog
    op.create_table(
        "probe_strategies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("philosophy", sa.String(500), nullable=False),
        sa.Column("strategy_type", sa.String(50), nullable=False),
        sa.Column("direction", sa.String(15), nullable=False),
        sa.Column("details", JSONB, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_probe_strategies_name", "probe_strategies", ["name"])
    op.create_index("ix_probe_strategies_type", "probe_strategies", ["strategy_type"])

    # Aggregated probe results
    op.create_table(
        "strategy_probe_results",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(50), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column(
            "strategy_id", sa.Integer,
            sa.ForeignKey("probe_strategies.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        # Dimensions
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("risk_profile", sa.String(10), nullable=False),
        sa.Column("open_day", sa.Integer, nullable=False),
        sa.Column("open_hour", sa.Integer, nullable=False),
        sa.Column("long_short", sa.String(5), nullable=False),
        # Aggregations
        sa.Column("num_trades", sa.Integer, nullable=False),
        sa.Column("pnl_mean", sa.Float, nullable=False),
        sa.Column("pnl_std", sa.Float, nullable=False),
        sa.Column("max_drawdown", sa.Float, nullable=False),
        sa.Column("max_profit", sa.Float, nullable=False),
        # Optional
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # Unique constraint
        sa.UniqueConstraint(
            "run_id", "symbol", "strategy_id", "timeframe", "risk_profile",
            "open_day", "open_hour", "long_short",
            name="uq_probe_result_dimensions",
        ),
    )
    op.create_index("ix_probe_run_id", "strategy_probe_results", ["run_id"])
    op.create_index("ix_probe_strat_tf_risk", "strategy_probe_results", ["strategy_id", "timeframe", "risk_profile"])
    op.create_index("ix_probe_symbol_run", "strategy_probe_results", ["symbol", "run_id"])


def downgrade() -> None:
    op.drop_table("strategy_probe_results")
    op.drop_table("probe_strategies")
