"""Create trading agents tables.

Creates tables for:
- agent_strategies: Strategy definitions (predefined + custom)
- trading_agents: Agent instances
- agent_orders: Orders placed by agents
- agent_activity_log: Audit trail

Revision ID: 036
Revises: 035
Create Date: 2026-02-17
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers
revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- agent_strategies ---
    op.create_table(
        "agent_strategies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False, server_default="long_short"),
        sa.Column("entry_long", postgresql.JSONB(), nullable=True),
        sa.Column("entry_short", postgresql.JSONB(), nullable=True),
        sa.Column("exit_long", postgresql.JSONB(), nullable=True),
        sa.Column("exit_short", postgresql.JSONB(), nullable=True),
        sa.Column("atr_stop_mult", sa.Float(), nullable=True),
        sa.Column("atr_target_mult", sa.Float(), nullable=True),
        sa.Column("trailing_atr_mult", sa.Float(), nullable=True),
        sa.Column("time_stop_bars", sa.Integer(), nullable=True),
        sa.Column("required_features", postgresql.JSONB(), nullable=True),
        sa.Column("is_predefined", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("source_strategy_id", sa.Integer(), nullable=True),
        sa.Column("cloned_from_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["account_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cloned_from_id"], ["agent_strategies.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "category IN ('trend', 'mean_reversion', 'breakout', 'volume_flow', 'pattern', 'regime', 'custom')",
            name="ck_agent_strategy_category",
        ),
        sa.CheckConstraint(
            "direction IN ('long_short', 'long_only', 'short_only')",
            name="ck_agent_strategy_direction",
        ),
        sa.UniqueConstraint("account_id", "name", name="uq_agent_strategy_account_name"),
    )
    op.create_index("ix_agent_strategies_account_id", "agent_strategies", ["account_id"])
    op.create_index("ix_agent_strategies_category", "agent_strategies", ["category"])
    op.create_index("ix_agent_strategies_is_predefined", "agent_strategies", ["is_predefined"])

    # --- trading_agents ---
    op.create_table(
        "trading_agents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("strategy_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="created"),
        sa.Column("timeframe", sa.String(10), nullable=False, server_default="5Min"),
        sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("lookback_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("position_size_dollars", sa.Float(), nullable=False, server_default="1000.0"),
        sa.Column("risk_config", postgresql.JSONB(), nullable=True),
        sa.Column("exit_config", postgresql.JSONB(), nullable=True),
        sa.Column("paper", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_signal", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("consecutive_errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_position", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["account_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_id"], ["agent_strategies.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('created', 'active', 'paused', 'stopped', 'error')",
            name="ck_trading_agent_status",
        ),
        sa.CheckConstraint(
            "timeframe IN ('1Min', '5Min', '15Min', '1Hour', '1Day')",
            name="ck_trading_agent_timeframe",
        ),
        sa.UniqueConstraint("account_id", "name", name="uq_trading_agent_account_name"),
    )
    op.create_index("ix_trading_agents_account_id", "trading_agents", ["account_id"])
    op.create_index("ix_trading_agents_status", "trading_agents", ["status"])
    op.create_index("ix_trading_agents_account_status", "trading_agents", ["account_id", "status"])

    # --- agent_orders ---
    op.create_table(
        "agent_orders",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("order_type", sa.String(20), nullable=False, server_default="market"),
        sa.Column("limit_price", sa.Float(), nullable=True),
        sa.Column("stop_price", sa.Float(), nullable=True),
        sa.Column("client_order_id", sa.String(100), nullable=False, unique=True),
        sa.Column("broker_order_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("filled_quantity", sa.Float(), nullable=True),
        sa.Column("filled_avg_price", sa.Float(), nullable=True),
        sa.Column("signal_direction", sa.String(20), nullable=True),
        sa.Column("signal_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("risk_violations", postgresql.JSONB(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agent_id"], ["trading_agents.id"], ondelete="CASCADE"),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_agent_order_side"),
        sa.CheckConstraint(
            "status IN ('pending', 'submitted', 'accepted', 'filled', 'partially_filled', 'cancelled', 'rejected', 'expired')",
            name="ck_agent_order_status",
        ),
    )
    op.create_index("ix_agent_orders_agent_id", "agent_orders", ["agent_id"])
    op.create_index("ix_agent_orders_account_id", "agent_orders", ["account_id"])
    op.create_index("ix_agent_orders_agent_created", "agent_orders", ["agent_id", "created_at"])

    # --- agent_activity_log ---
    op.create_table(
        "agent_activity_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("activity_type", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("severity", sa.String(10), nullable=False, server_default="info"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agent_id"], ["trading_agents.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "severity IN ('debug', 'info', 'warn', 'error')",
            name="ck_agent_activity_severity",
        ),
    )
    op.create_index("ix_agent_activity_agent_id", "agent_activity_log", ["agent_id"])
    op.create_index("ix_agent_activity_agent_created", "agent_activity_log", ["agent_id", "created_at"])
    op.create_index("ix_agent_activity_account_type", "agent_activity_log", ["account_id", "activity_type"])


def downgrade() -> None:
    op.drop_table("agent_activity_log")
    op.drop_table("agent_orders")
    op.drop_table("trading_agents")
    op.drop_table("agent_strategies")
