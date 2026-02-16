"""Restructure trade lifecycle schema.

Simplifies trade lifecycle to: fills are the atomic unit, decision_contexts
capture trader reasoning per fill, campaigns are derived/computed groupings.

Drops:
- trade_intents, trade_evaluations, trade_evaluation_items
- position_lots, lot_closures
- position_campaigns, campaign_legs, leg_fill_map

Restructures:
- trade_fills: removes intent_id column
- decision_contexts: removes campaign_id/leg_id/intent_id, adds fill_id (unique)
- campaign_checks: removes leg_id, adds decision_context_id

Creates:
- campaigns (lightweight derived grouping)
- campaign_fills (junction table)

Revision ID: 026
Revises: 025
Create Date: 2026-02-15
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Drop FK constraints referencing tables being removed
    # ------------------------------------------------------------------

    # trade_fills.intent_id → trade_intents
    op.drop_constraint("trade_fills_intent_id_fkey", "trade_fills", type_="foreignkey")

    # position_campaigns.intent_id → trade_intents
    op.drop_constraint(
        "position_campaigns_intent_id_fkey", "position_campaigns", type_="foreignkey"
    )

    # campaign_legs.intent_id → trade_intents
    op.drop_constraint("campaign_legs_intent_id_fkey", "campaign_legs", type_="foreignkey")

    # campaign_legs.campaign_id → position_campaigns
    op.drop_constraint(
        "campaign_legs_campaign_id_fkey", "campaign_legs", type_="foreignkey"
    )

    # decision_contexts.campaign_id → position_campaigns
    op.drop_constraint(
        "decision_contexts_campaign_id_fkey", "decision_contexts", type_="foreignkey"
    )
    # decision_contexts.leg_id → campaign_legs
    op.drop_constraint(
        "decision_contexts_leg_id_fkey", "decision_contexts", type_="foreignkey"
    )
    # decision_contexts.intent_id → trade_intents
    op.drop_constraint(
        "decision_contexts_intent_id_fkey", "decision_contexts", type_="foreignkey"
    )

    # campaign_checks.leg_id → campaign_legs
    op.drop_constraint(
        "campaign_checks_leg_id_fkey", "campaign_checks", type_="foreignkey"
    )

    # trade_evaluations.intent_id → trade_intents
    op.drop_constraint(
        "trade_evaluations_intent_id_fkey", "trade_evaluations", type_="foreignkey"
    )
    # trade_evaluations.campaign_id → position_campaigns
    op.drop_constraint(
        "trade_evaluations_campaign_id_fkey", "trade_evaluations", type_="foreignkey"
    )
    # trade_evaluations.leg_id → campaign_legs
    op.drop_constraint(
        "trade_evaluations_leg_id_fkey", "trade_evaluations", type_="foreignkey"
    )

    # position_lots.campaign_id → position_campaigns
    op.drop_constraint(
        "position_lots_campaign_id_fkey", "position_lots", type_="foreignkey"
    )

    # ------------------------------------------------------------------
    # 2. Drop tables in dependency order
    # ------------------------------------------------------------------
    op.drop_table("leg_fill_map")
    op.drop_table("trade_evaluation_items")
    op.drop_table("trade_evaluations")
    op.drop_table("campaign_legs")
    op.drop_table("lot_closures")
    op.drop_table("position_lots")
    op.drop_table("position_campaigns")
    op.drop_table("trade_intents")

    # ------------------------------------------------------------------
    # 3. Remove intent_id column from trade_fills
    # ------------------------------------------------------------------
    op.drop_column("trade_fills", "intent_id")

    # ------------------------------------------------------------------
    # 4. Restructure decision_contexts
    #    Drop: campaign_id, leg_id, intent_id
    #    Add: fill_id (BigInteger, FK → trade_fills.id, UNIQUE, NOT NULL)
    # ------------------------------------------------------------------
    # Drop old indexes that reference removed columns
    op.drop_index("ix_decision_contexts_account_campaign", table_name="decision_contexts")

    op.drop_column("decision_contexts", "campaign_id")
    op.drop_column("decision_contexts", "leg_id")
    op.drop_column("decision_contexts", "intent_id")

    # Add fill_id — initially nullable to allow migration, then NOT NULL
    op.add_column(
        "decision_contexts",
        sa.Column("fill_id", sa.BigInteger(), nullable=True),
    )

    # Backfill: delete orphan decision_contexts that don't have a fill_id
    # (since we can't reconstruct the link, these are no longer useful)
    op.execute("DELETE FROM decision_contexts WHERE fill_id IS NULL")

    # Now make it NOT NULL and UNIQUE
    op.alter_column("decision_contexts", "fill_id", nullable=False)
    op.create_unique_constraint("uq_decision_contexts_fill_id", "decision_contexts", ["fill_id"])
    op.create_foreign_key(
        "decision_contexts_fill_id_fkey",
        "decision_contexts",
        "trade_fills",
        ["fill_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Add new index
    op.create_index(
        "ix_decision_contexts_account_fill",
        "decision_contexts",
        ["account_id", "fill_id"],
    )

    # ------------------------------------------------------------------
    # 5. Restructure campaign_checks
    #    Drop: leg_id
    #    Add: decision_context_id (BigInteger, FK → decision_contexts.id)
    # ------------------------------------------------------------------
    # Drop old indexes that reference leg_id
    op.drop_index("ix_campaign_checks_leg_id", table_name="campaign_checks")

    op.drop_column("campaign_checks", "leg_id")

    op.add_column(
        "campaign_checks",
        sa.Column("decision_context_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "campaign_checks_decision_context_id_fkey",
        "campaign_checks",
        "decision_contexts",
        ["decision_context_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_campaign_checks_decision_context",
        "campaign_checks",
        ["decision_context_id"],
    )

    # ------------------------------------------------------------------
    # 6. Create new campaigns table
    # ------------------------------------------------------------------
    op.create_table(
        "campaigns",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column(
            "strategy_id",
            sa.Integer(),
            sa.ForeignKey("strategies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_campaigns_account_symbol_strategy",
        "campaigns",
        ["account_id", "symbol", "strategy_id"],
    )

    # ------------------------------------------------------------------
    # 7. Create campaign_fills junction table
    # ------------------------------------------------------------------
    op.create_table(
        "campaign_fills",
        sa.Column(
            "campaign_id",
            sa.BigInteger(),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "fill_id",
            sa.BigInteger(),
            sa.ForeignKey("trade_fills.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    # ------------------------------------------------------------------
    # Reverse: drop new tables
    # ------------------------------------------------------------------
    op.drop_table("campaign_fills")
    op.drop_index("ix_campaigns_account_symbol_strategy", table_name="campaigns")
    op.drop_table("campaigns")

    # ------------------------------------------------------------------
    # Reverse: campaign_checks — restore leg_id, drop decision_context_id
    # ------------------------------------------------------------------
    op.drop_index("ix_campaign_checks_decision_context", table_name="campaign_checks")
    op.drop_constraint(
        "campaign_checks_decision_context_id_fkey", "campaign_checks", type_="foreignkey"
    )
    op.drop_column("campaign_checks", "decision_context_id")

    # Restore leg_id (nullable since we can't restore data)
    op.add_column(
        "campaign_checks",
        sa.Column("leg_id", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_campaign_checks_leg_id", "campaign_checks", ["leg_id"])

    # ------------------------------------------------------------------
    # Reverse: decision_contexts — restore campaign_id/leg_id/intent_id
    # ------------------------------------------------------------------
    op.drop_index("ix_decision_contexts_account_fill", table_name="decision_contexts")
    op.drop_constraint(
        "decision_contexts_fill_id_fkey", "decision_contexts", type_="foreignkey"
    )
    op.drop_constraint("uq_decision_contexts_fill_id", "decision_contexts", type_="unique")
    op.drop_column("decision_contexts", "fill_id")

    op.add_column(
        "decision_contexts",
        sa.Column("campaign_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "decision_contexts",
        sa.Column("leg_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "decision_contexts",
        sa.Column("intent_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_decision_contexts_account_campaign",
        "decision_contexts",
        ["account_id", "campaign_id"],
    )

    # ------------------------------------------------------------------
    # Reverse: restore intent_id on trade_fills
    # ------------------------------------------------------------------
    op.add_column(
        "trade_fills",
        sa.Column("intent_id", sa.BigInteger(), nullable=True),
    )

    # ------------------------------------------------------------------
    # Reverse: recreate dropped tables (structure only, no data)
    # ------------------------------------------------------------------

    # trade_intents
    op.create_table(
        "trade_intents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("stop_loss", sa.Float(), nullable=False),
        sa.Column("profit_target", sa.Float(), nullable=False),
        sa.Column("position_size", sa.Float(), nullable=True),
        sa.Column("position_value", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column(
            "strategy_id",
            sa.Integer(),
            sa.ForeignKey("strategies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("intent_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # position_campaigns
    op.create_table(
        "position_campaigns",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("qty_opened", sa.Float(), nullable=True),
        sa.Column("qty_closed", sa.Float(), nullable=True),
        sa.Column("avg_open_price", sa.Float(), nullable=True),
        sa.Column("avg_close_price", sa.Float(), nullable=True),
        sa.Column("realized_pnl", sa.Float(), nullable=True),
        sa.Column("return_pct", sa.Float(), nullable=True),
        sa.Column("holding_period_sec", sa.Integer(), nullable=True),
        sa.Column("num_fills", sa.Integer(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("derived_from", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),
        sa.Column("max_qty", sa.Float(), nullable=True),
        sa.Column("cost_basis_method", sa.String(10), nullable=False, server_default="average"),
        sa.Column("source", sa.String(20), nullable=False, server_default="broker_synced"),
        sa.Column("link_group_id", sa.BigInteger(), nullable=True),
        sa.Column("r_multiple", sa.Float(), nullable=True),
        sa.Column(
            "intent_id",
            sa.BigInteger(),
            sa.ForeignKey("trade_intents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # position_lots
    op.create_table(
        "position_lots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "open_fill_id",
            sa.BigInteger(),
            sa.ForeignKey("trade_fills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("open_qty", sa.Float(), nullable=False),
        sa.Column("remaining_qty", sa.Float(), nullable=False),
        sa.Column("avg_open_price", sa.Float(), nullable=False),
        sa.Column(
            "strategy_id",
            sa.Integer(),
            sa.ForeignKey("strategies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),
        sa.Column(
            "campaign_id",
            sa.BigInteger(),
            sa.ForeignKey("position_campaigns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # lot_closures
    op.create_table(
        "lot_closures",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "lot_id",
            sa.BigInteger(),
            sa.ForeignKey("position_lots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "open_fill_id",
            sa.BigInteger(),
            sa.ForeignKey("trade_fills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "close_fill_id",
            sa.BigInteger(),
            sa.ForeignKey("trade_fills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("matched_qty", sa.Float(), nullable=False),
        sa.Column("open_price", sa.Float(), nullable=False),
        sa.Column("close_price", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=True),
        sa.Column("fees_allocated", sa.Float(), nullable=True),
        sa.Column("match_method", sa.String(10), nullable=False, server_default="fifo"),
        sa.Column("matched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # campaign_legs
    op.create_table(
        "campaign_legs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "campaign_id",
            sa.BigInteger(),
            sa.ForeignKey("position_campaigns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("leg_type", sa.String(20), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("avg_price", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fill_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "intent_id",
            sa.BigInteger(),
            sa.ForeignKey("trade_intents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # leg_fill_map
    op.create_table(
        "leg_fill_map",
        sa.Column(
            "leg_id",
            sa.BigInteger(),
            sa.ForeignKey("campaign_legs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "fill_id",
            sa.BigInteger(),
            sa.ForeignKey("trade_fills.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("allocated_qty", sa.Float(), nullable=True),
    )

    # trade_evaluations
    op.create_table(
        "trade_evaluations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "intent_id",
            sa.BigInteger(),
            sa.ForeignKey("trade_intents.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "campaign_id",
            sa.BigInteger(),
            sa.ForeignKey("position_campaigns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "leg_id",
            sa.BigInteger(),
            sa.ForeignKey("campaign_legs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("eval_scope", sa.String(20), nullable=False, server_default="intent"),
        sa.Column("overall_label", sa.String(20), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("blocker_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("critical_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("info_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evaluators_run", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    # trade_evaluation_items
    op.create_table(
        "trade_evaluation_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "evaluation_id",
            sa.BigInteger(),
            sa.ForeignKey("trade_evaluations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("evaluator", sa.String(100), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("severity_priority", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("dimension_key", sa.String(50), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("visuals", postgresql.JSONB(), nullable=True),
    )

    # ------------------------------------------------------------------
    # Restore FK constraints
    # ------------------------------------------------------------------
    op.create_foreign_key(
        "trade_fills_intent_id_fkey",
        "trade_fills",
        "trade_intents",
        ["intent_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Restore decision_contexts FKs
    op.create_foreign_key(
        "decision_contexts_campaign_id_fkey",
        "decision_contexts",
        "position_campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "decision_contexts_leg_id_fkey",
        "decision_contexts",
        "campaign_legs",
        ["leg_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "decision_contexts_intent_id_fkey",
        "decision_contexts",
        "trade_intents",
        ["intent_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Restore campaign_checks FK
    op.create_foreign_key(
        "campaign_checks_leg_id_fkey",
        "campaign_checks",
        "campaign_legs",
        ["leg_id"],
        ["id"],
        ondelete="CASCADE",
    )
