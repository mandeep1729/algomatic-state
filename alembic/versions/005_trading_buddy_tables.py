"""Add Trading Buddy tables.

This migration adds tables for the Trading Buddy platform:
- user_accounts: User trading accounts with risk parameters
- user_rules: Custom evaluation rules per user
- trade_intents: User trade proposals
- trade_evaluations: Evaluation results
- trade_evaluation_items: Individual evaluation findings

Revision ID: 005
Revises: 004
Create Date: 2026-01-31 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Trading Buddy tables."""
    # 1. Create user_accounts table
    op.create_table(
        "user_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_user_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("account_balance", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("max_position_size_pct", sa.Float(), nullable=False, server_default="5.0"),
        sa.Column("max_risk_per_trade_pct", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("max_daily_loss_pct", sa.Float(), nullable=False, server_default="3.0"),
        sa.Column("min_risk_reward_ratio", sa.Float(), nullable=False, server_default="2.0"),
        sa.Column("default_timeframes", postgresql.JSONB(), nullable=False,
                  server_default='["1Min", "5Min", "15Min", "1Hour"]'),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_user_id", name="uq_user_accounts_external_id"),
        sa.CheckConstraint("account_balance >= 0", name="ck_account_balance_positive"),
        sa.CheckConstraint("max_position_size_pct > 0 AND max_position_size_pct <= 100",
                           name="ck_max_position_pct_range"),
        sa.CheckConstraint("max_risk_per_trade_pct > 0 AND max_risk_per_trade_pct <= 100",
                           name="ck_max_risk_pct_range"),
        sa.CheckConstraint("max_daily_loss_pct > 0 AND max_daily_loss_pct <= 100",
                           name="ck_max_daily_loss_range"),
        sa.CheckConstraint("min_risk_reward_ratio > 0", name="ck_min_rr_positive"),
    )
    op.create_index("ix_user_accounts_external_id", "user_accounts", ["external_user_id"])

    # 2. Create user_rules table
    op.create_table(
        "user_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("rule_code", sa.String(50), nullable=False),
        sa.Column("evaluator", sa.String(100), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["account_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("account_id", "rule_code", name="uq_user_rule_account_code"),
    )
    op.create_index("ix_user_rules_account_id", "user_rules", ["account_id"])
    op.create_index("ix_user_rules_evaluator", "user_rules", ["evaluator"])

    # 3. Create trade_intents table
    op.create_table(
        "trade_intents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("stop_loss", sa.Float(), nullable=False),
        sa.Column("profit_target", sa.Float(), nullable=False),
        sa.Column("position_size", sa.Float(), nullable=True),
        sa.Column("position_value", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("intent_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["account_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.CheckConstraint("direction IN ('long', 'short')", name="ck_intent_direction"),
        sa.CheckConstraint("entry_price > 0", name="ck_intent_entry_positive"),
        sa.CheckConstraint("stop_loss > 0", name="ck_intent_stop_positive"),
        sa.CheckConstraint("profit_target > 0", name="ck_intent_target_positive"),
        sa.CheckConstraint("position_size IS NULL OR position_size > 0",
                           name="ck_intent_size_positive"),
    )
    op.create_index("ix_trade_intents_account_id", "trade_intents", ["account_id"])
    op.create_index("ix_trade_intents_symbol", "trade_intents", ["symbol"])
    op.create_index("ix_trade_intents_status", "trade_intents", ["status"])
    op.create_index("ix_trade_intents_created", "trade_intents", ["created_at"])
    op.create_index("ix_trade_intents_symbol_status", "trade_intents", ["symbol", "status"])

    # 4. Create trade_evaluations table
    op.create_table(
        "trade_evaluations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("intent_id", sa.BigInteger(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("blocker_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("critical_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("info_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evaluators_run", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["intent_id"], ["trade_intents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("intent_id", name="uq_trade_evaluations_intent"),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_eval_score_range"),
        sa.CheckConstraint("blocker_count >= 0", name="ck_eval_blocker_count"),
        sa.CheckConstraint("critical_count >= 0", name="ck_eval_critical_count"),
        sa.CheckConstraint("warning_count >= 0", name="ck_eval_warning_count"),
        sa.CheckConstraint("info_count >= 0", name="ck_eval_info_count"),
    )
    op.create_index("ix_trade_evaluations_intent_id", "trade_evaluations", ["intent_id"])
    op.create_index("ix_trade_evaluations_score", "trade_evaluations", ["score"])

    # 5. Create trade_evaluation_items table
    op.create_table(
        "trade_evaluation_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("evaluation_id", sa.BigInteger(), nullable=False),
        sa.Column("evaluator", sa.String(100), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("severity_priority", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["evaluation_id"], ["trade_evaluations.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'critical', 'blocker')",
            name="ck_item_severity"
        ),
    )
    op.create_index("ix_eval_items_evaluation_id", "trade_evaluation_items", ["evaluation_id"])
    op.create_index("ix_eval_items_evaluator", "trade_evaluation_items", ["evaluator"])
    op.create_index("ix_eval_items_severity", "trade_evaluation_items", ["severity"])


def downgrade() -> None:
    """Drop Trading Buddy tables."""
    # Drop in reverse order of creation (respect foreign key constraints)
    op.drop_table("trade_evaluation_items")
    op.drop_table("trade_evaluations")
    op.drop_table("trade_intents")
    op.drop_table("user_rules")
    op.drop_table("user_accounts")
