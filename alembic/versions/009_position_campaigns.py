"""Position campaigns: evolve round_trips, add campaign legs, decision contexts.

This migration:
1. Adds source column to trade_fills
2. Adds hypothesis, strategy_tags to trade_intents
3. Renames round_trips → position_campaigns, adds new columns
4. Creates campaign_legs table
5. Creates leg_fill_map table
6. Creates decision_contexts table
7. Adds campaign_id to position_lots
8. Evolves trade_evaluations for multi-scope evaluation
9. Adds dimension_key, visuals to trade_evaluation_items

Revision ID: 009
Revises: 008
Create Date: 2026-02-06 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # Step 1: Add source column to trade_fills
    # -------------------------------------------------------------------------
    op.add_column(
        "trade_fills",
        sa.Column("source", sa.String(20), nullable=True, server_default="broker_synced"),
    )
    op.create_check_constraint(
        "ck_trade_fill_source",
        "trade_fills",
        "source IN ('broker_synced', 'manual', 'proposed')",
    )

    # -------------------------------------------------------------------------
    # Step 2: Add hypothesis, strategy_tags to trade_intents
    # -------------------------------------------------------------------------
    op.add_column(
        "trade_intents",
        sa.Column("hypothesis", sa.Text(), nullable=True),
    )
    op.add_column(
        "trade_intents",
        sa.Column("strategy_tags", postgresql.JSONB(), nullable=False, server_default="[]"),
    )

    # -------------------------------------------------------------------------
    # Step 3: Rename round_trips → position_campaigns, add new columns
    # -------------------------------------------------------------------------
    op.rename_table("round_trips", "position_campaigns")

    # Rename existing indexes to match new table name
    op.execute(
        "ALTER INDEX IF EXISTS ix_round_trips_symbol "
        "RENAME TO ix_position_campaigns_symbol"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_round_trips_account_symbol "
        "RENAME TO ix_position_campaigns_account_symbol"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_round_trips_account_closed "
        "RENAME TO ix_position_campaigns_account_closed"
    )

    # Rename existing check constraint
    op.execute(
        "ALTER TABLE position_campaigns "
        "RENAME CONSTRAINT ck_rt_direction TO ck_campaign_direction"
    )

    # Add new columns
    op.add_column(
        "position_campaigns",
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),
    )
    op.add_column(
        "position_campaigns",
        sa.Column("max_qty", sa.Float(), nullable=True),
    )
    op.add_column(
        "position_campaigns",
        sa.Column("cost_basis_method", sa.String(10), nullable=False, server_default="average"),
    )
    op.add_column(
        "position_campaigns",
        sa.Column("source", sa.String(20), nullable=False, server_default="broker_synced"),
    )
    op.add_column(
        "position_campaigns",
        sa.Column("link_group_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "position_campaigns",
        sa.Column("r_multiple", sa.Float(), nullable=True),
    )
    op.add_column(
        "position_campaigns",
        sa.Column(
            "intent_id",
            sa.BigInteger(),
            sa.ForeignKey("trade_intents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "position_campaigns",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )

    # Add new constraints
    op.create_check_constraint(
        "ck_campaign_status",
        "position_campaigns",
        "status IN ('open', 'closed')",
    )
    op.create_check_constraint(
        "ck_campaign_cost_basis",
        "position_campaigns",
        "cost_basis_method IN ('average', 'fifo', 'lifo')",
    )
    op.create_check_constraint(
        "ck_campaign_source",
        "position_campaigns",
        "source IN ('broker_synced', 'manual', 'proposed')",
    )

    # Add new index
    op.create_index(
        "ix_position_campaigns_account_status",
        "position_campaigns",
        ["account_id", "status"],
    )

    # -------------------------------------------------------------------------
    # Step 4: Create campaign_legs table
    # -------------------------------------------------------------------------
    op.create_table(
        "campaign_legs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "campaign_id",
            sa.BigInteger(),
            sa.ForeignKey("position_campaigns.id", ondelete="CASCADE"),
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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Constraints
        sa.CheckConstraint(
            "leg_type IN ('open', 'add', 'reduce', 'close', 'flip_close', 'flip_open')",
            name="ck_leg_type",
        ),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_leg_side"),
        sa.CheckConstraint("quantity > 0", name="ck_leg_qty_positive"),
    )
    op.create_index(
        "ix_campaign_legs_campaign_started",
        "campaign_legs",
        ["campaign_id", "started_at"],
    )

    # -------------------------------------------------------------------------
    # Step 5: Create leg_fill_map table
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # Step 6: Create decision_contexts table
    # -------------------------------------------------------------------------
    op.create_table(
        "decision_contexts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            sa.BigInteger(),
            sa.ForeignKey("position_campaigns.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "leg_id",
            sa.BigInteger(),
            sa.ForeignKey("campaign_legs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "intent_id",
            sa.BigInteger(),
            sa.ForeignKey("trade_intents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("context_type", sa.String(30), nullable=False),
        sa.Column("strategy_tags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column("exit_intent", postgresql.JSONB(), nullable=True),
        sa.Column("feelings_then", postgresql.JSONB(), nullable=True),
        sa.Column("feelings_now", postgresql.JSONB(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Constraints
        sa.CheckConstraint(
            "context_type IN ('entry', 'add', 'reduce', 'exit', 'idea', 'post_trade_reflection')",
            name="ck_context_type",
        ),
    )
    op.create_index(
        "ix_decision_contexts_account_campaign",
        "decision_contexts",
        ["account_id", "campaign_id"],
    )
    op.create_index(
        "ix_decision_contexts_account_created",
        "decision_contexts",
        ["account_id", "created_at"],
    )

    # -------------------------------------------------------------------------
    # Step 7: Add campaign_id to position_lots
    # -------------------------------------------------------------------------
    op.add_column(
        "position_lots",
        sa.Column(
            "campaign_id",
            sa.BigInteger(),
            sa.ForeignKey("position_campaigns.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # -------------------------------------------------------------------------
    # Step 8: Evolve trade_evaluations for multi-scope
    # -------------------------------------------------------------------------
    # Make intent_id nullable
    op.alter_column(
        "trade_evaluations",
        "intent_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )

    # Drop the unique constraint on intent_id
    op.drop_constraint("trade_evaluations_intent_id_key", "trade_evaluations", type_="unique")

    # Add new columns
    op.add_column(
        "trade_evaluations",
        sa.Column(
            "campaign_id",
            sa.BigInteger(),
            sa.ForeignKey("position_campaigns.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "trade_evaluations",
        sa.Column(
            "leg_id",
            sa.BigInteger(),
            sa.ForeignKey("campaign_legs.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "trade_evaluations",
        sa.Column("eval_scope", sa.String(20), nullable=False, server_default="intent"),
    )
    op.add_column(
        "trade_evaluations",
        sa.Column("overall_label", sa.String(20), nullable=True),
    )

    # Add constraints
    op.create_check_constraint(
        "ck_eval_scope",
        "trade_evaluations",
        "eval_scope IN ('intent', 'campaign', 'leg')",
    )
    op.create_check_constraint(
        "ck_eval_overall_label",
        "trade_evaluations",
        "overall_label IS NULL OR overall_label IN ('aligned', 'mixed', 'fragile', 'deviates')",
    )

    # Add indexes for new FK columns
    op.create_index("ix_trade_evaluations_campaign", "trade_evaluations", ["campaign_id"])
    op.create_index("ix_trade_evaluations_leg", "trade_evaluations", ["leg_id"])

    # Partial unique indexes: one evaluation per scope target
    op.execute(
        "CREATE UNIQUE INDEX uq_eval_intent_scope "
        "ON trade_evaluations (intent_id) "
        "WHERE eval_scope = 'intent' AND intent_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_eval_campaign_scope "
        "ON trade_evaluations (campaign_id) "
        "WHERE eval_scope = 'campaign' AND campaign_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_eval_leg_scope "
        "ON trade_evaluations (leg_id) "
        "WHERE eval_scope = 'leg' AND leg_id IS NOT NULL"
    )

    # -------------------------------------------------------------------------
    # Step 9: Add dimension_key, visuals to trade_evaluation_items
    # -------------------------------------------------------------------------
    op.add_column(
        "trade_evaluation_items",
        sa.Column("dimension_key", sa.String(50), nullable=True),
    )
    op.add_column(
        "trade_evaluation_items",
        sa.Column("visuals", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    # -------------------------------------------------------------------------
    # Reverse Step 9: Drop dimension_key, visuals from trade_evaluation_items
    # -------------------------------------------------------------------------
    op.drop_column("trade_evaluation_items", "visuals")
    op.drop_column("trade_evaluation_items", "dimension_key")

    # -------------------------------------------------------------------------
    # Reverse Step 8: Revert trade_evaluations
    # -------------------------------------------------------------------------
    # Drop partial unique indexes
    op.execute("DROP INDEX IF EXISTS uq_eval_leg_scope")
    op.execute("DROP INDEX IF EXISTS uq_eval_campaign_scope")
    op.execute("DROP INDEX IF EXISTS uq_eval_intent_scope")

    # Drop indexes
    op.drop_index("ix_trade_evaluations_leg", table_name="trade_evaluations")
    op.drop_index("ix_trade_evaluations_campaign", table_name="trade_evaluations")

    # Drop constraints
    op.drop_constraint("ck_eval_overall_label", "trade_evaluations", type_="check")
    op.drop_constraint("ck_eval_scope", "trade_evaluations", type_="check")

    # Drop new columns
    op.drop_column("trade_evaluations", "overall_label")
    op.drop_column("trade_evaluations", "eval_scope")
    op.drop_column("trade_evaluations", "leg_id")
    op.drop_column("trade_evaluations", "campaign_id")

    # Restore unique constraint on intent_id
    op.create_unique_constraint(
        "trade_evaluations_intent_id_key", "trade_evaluations", ["intent_id"]
    )

    # Make intent_id NOT NULL again
    op.alter_column(
        "trade_evaluations",
        "intent_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Reverse Step 7: Drop campaign_id from position_lots
    # -------------------------------------------------------------------------
    op.drop_column("position_lots", "campaign_id")

    # -------------------------------------------------------------------------
    # Reverse Step 6: Drop decision_contexts
    # -------------------------------------------------------------------------
    op.drop_table("decision_contexts")

    # -------------------------------------------------------------------------
    # Reverse Step 5: Drop leg_fill_map
    # -------------------------------------------------------------------------
    op.drop_table("leg_fill_map")

    # -------------------------------------------------------------------------
    # Reverse Step 4: Drop campaign_legs
    # -------------------------------------------------------------------------
    op.drop_table("campaign_legs")

    # -------------------------------------------------------------------------
    # Reverse Step 3: Revert position_campaigns → round_trips
    # -------------------------------------------------------------------------
    # Drop new constraints
    op.drop_constraint("ck_campaign_source", "position_campaigns", type_="check")
    op.drop_constraint("ck_campaign_cost_basis", "position_campaigns", type_="check")
    op.drop_constraint("ck_campaign_status", "position_campaigns", type_="check")

    # Drop new index
    op.drop_index("ix_position_campaigns_account_status", table_name="position_campaigns")

    # Drop new columns
    op.drop_column("position_campaigns", "updated_at")
    op.drop_column("position_campaigns", "intent_id")
    op.drop_column("position_campaigns", "r_multiple")
    op.drop_column("position_campaigns", "link_group_id")
    op.drop_column("position_campaigns", "source")
    op.drop_column("position_campaigns", "cost_basis_method")
    op.drop_column("position_campaigns", "max_qty")
    op.drop_column("position_campaigns", "status")

    # Rename constraint back
    op.execute(
        "ALTER TABLE position_campaigns "
        "RENAME CONSTRAINT ck_campaign_direction TO ck_rt_direction"
    )

    # Rename indexes back
    op.execute(
        "ALTER INDEX IF EXISTS ix_position_campaigns_account_closed "
        "RENAME TO ix_round_trips_account_closed"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_position_campaigns_account_symbol "
        "RENAME TO ix_round_trips_account_symbol"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_position_campaigns_symbol "
        "RENAME TO ix_round_trips_symbol"
    )

    # Rename table back
    op.rename_table("position_campaigns", "round_trips")

    # -------------------------------------------------------------------------
    # Reverse Step 2: Drop hypothesis, strategy_tags from trade_intents
    # -------------------------------------------------------------------------
    op.drop_column("trade_intents", "strategy_tags")
    op.drop_column("trade_intents", "hypothesis")

    # -------------------------------------------------------------------------
    # Reverse Step 1: Drop source from trade_fills
    # -------------------------------------------------------------------------
    op.drop_constraint("ck_trade_fill_source", "trade_fills", type_="check")
    op.drop_column("trade_fills", "source")
