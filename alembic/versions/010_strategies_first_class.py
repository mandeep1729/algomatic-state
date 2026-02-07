"""Strategies as first-class entity: normalized strategy table, FK references.

This migration:
1. Creates strategies table (user-scoped, unique name per account)
2. Adds strategy_id FK to position_lots, drops strategy_tag
3. Adds strategy_id FK to trade_intents, drops strategy_tags
4. Adds strategy_id FK to decision_contexts, drops strategy_tags
5. Adds strategy_id FK to position_campaigns

Revision ID: 010
Revises: 009
Create Date: 2026-02-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create strategies table
    op.create_table(
        "strategies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["account_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("account_id", "name", name="uq_strategy_account_name"),
    )
    op.create_index("ix_strategies_account_id", "strategies", ["account_id"])

    # 2. position_lots: add strategy_id FK, drop strategy_tag
    op.add_column(
        "position_lots",
        sa.Column("strategy_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_position_lots_strategy_id",
        "position_lots",
        "strategies",
        ["strategy_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_column("position_lots", "strategy_tag")

    # 3. trade_intents: add strategy_id FK, drop strategy_tags
    op.add_column(
        "trade_intents",
        sa.Column("strategy_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_trade_intents_strategy_id",
        "trade_intents",
        "strategies",
        ["strategy_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_column("trade_intents", "strategy_tags")

    # 4. decision_contexts: add strategy_id FK, drop strategy_tags
    op.add_column(
        "decision_contexts",
        sa.Column("strategy_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_decision_contexts_strategy_id",
        "decision_contexts",
        "strategies",
        ["strategy_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_column("decision_contexts", "strategy_tags")

    # 5. position_campaigns: add strategy_id FK (no column to drop)
    op.add_column(
        "position_campaigns",
        sa.Column("strategy_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_position_campaigns_strategy_id",
        "position_campaigns",
        "strategies",
        ["strategy_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # 5. position_campaigns: drop strategy_id FK
    op.drop_constraint("fk_position_campaigns_strategy_id", "position_campaigns", type_="foreignkey")
    op.drop_column("position_campaigns", "strategy_id")

    # 4. decision_contexts: drop strategy_id FK, restore strategy_tags
    op.drop_constraint("fk_decision_contexts_strategy_id", "decision_contexts", type_="foreignkey")
    op.drop_column("decision_contexts", "strategy_id")
    op.add_column(
        "decision_contexts",
        sa.Column("strategy_tags", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
    )

    # 3. trade_intents: drop strategy_id FK, restore strategy_tags
    op.drop_constraint("fk_trade_intents_strategy_id", "trade_intents", type_="foreignkey")
    op.drop_column("trade_intents", "strategy_id")
    op.add_column(
        "trade_intents",
        sa.Column("strategy_tags", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
    )

    # 2. position_lots: drop strategy_id FK, restore strategy_tag
    op.drop_constraint("fk_position_lots_strategy_id", "position_lots", type_="foreignkey")
    op.drop_column("position_lots", "strategy_id")
    op.add_column(
        "position_lots",
        sa.Column("strategy_tag", sa.String(100), nullable=True),
    )

    # 1. Drop strategies table
    op.drop_index("ix_strategies_account_id", table_name="strategies")
    op.drop_table("strategies")
