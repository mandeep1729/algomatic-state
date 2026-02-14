"""Campaign leg orphan support.

Legs survive campaign deletion:
- Add symbol, direction, account_id to campaign_legs (denormalized from campaign)
- Make campaign_legs.campaign_id nullable with SET NULL on delete
- Change decision_contexts.campaign_id to SET NULL on delete
- Change trade_evaluations.campaign_id to SET NULL on delete
- Add partial index for orphan queries
- Add check constraint for leg direction

Revision ID: 022
Revises: 021
Create Date: 2026-02-13
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # Step 1: Add denormalized columns to campaign_legs
    # -------------------------------------------------------------------------
    op.add_column(
        "campaign_legs",
        sa.Column("symbol", sa.String(20), nullable=True),
    )
    op.add_column(
        "campaign_legs",
        sa.Column("direction", sa.String(10), nullable=True),
    )
    op.add_column(
        "campaign_legs",
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # -------------------------------------------------------------------------
    # Step 2: Backfill from parent campaigns
    # -------------------------------------------------------------------------
    op.execute(
        """
        UPDATE campaign_legs cl
        SET symbol = pc.symbol,
            direction = pc.direction,
            account_id = pc.account_id
        FROM position_campaigns pc
        WHERE cl.campaign_id = pc.id
        """
    )

    # Make NOT NULL after backfill
    op.alter_column("campaign_legs", "symbol", nullable=False)
    op.alter_column("campaign_legs", "direction", nullable=False)
    op.alter_column("campaign_legs", "account_id", nullable=False)

    # -------------------------------------------------------------------------
    # Step 3: Add check constraint for direction
    # -------------------------------------------------------------------------
    op.create_check_constraint(
        "ck_leg_direction",
        "campaign_legs",
        "direction IN ('long', 'short')",
    )

    # -------------------------------------------------------------------------
    # Step 4: Change campaign_legs.campaign_id FK to SET NULL
    # -------------------------------------------------------------------------
    # PostgreSQL auto-generated name: campaign_legs_campaign_id_fkey
    op.drop_constraint(
        "campaign_legs_campaign_id_fkey", "campaign_legs", type_="foreignkey"
    )
    op.alter_column(
        "campaign_legs",
        "campaign_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.create_foreign_key(
        "campaign_legs_campaign_id_fkey",
        "campaign_legs",
        "position_campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # -------------------------------------------------------------------------
    # Step 5: Change decision_contexts.campaign_id FK to SET NULL
    # -------------------------------------------------------------------------
    op.drop_constraint(
        "decision_contexts_campaign_id_fkey",
        "decision_contexts",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "decision_contexts_campaign_id_fkey",
        "decision_contexts",
        "position_campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # -------------------------------------------------------------------------
    # Step 6: Change trade_evaluations.campaign_id FK to SET NULL
    # -------------------------------------------------------------------------
    op.drop_constraint(
        "trade_evaluations_campaign_id_fkey",
        "trade_evaluations",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "trade_evaluations_campaign_id_fkey",
        "trade_evaluations",
        "position_campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # -------------------------------------------------------------------------
    # Step 7: Partial index for orphan queries
    # -------------------------------------------------------------------------
    op.execute(
        "CREATE INDEX ix_campaign_legs_orphaned "
        "ON campaign_legs (account_id, symbol, started_at) "
        "WHERE campaign_id IS NULL"
    )


def downgrade() -> None:
    # Drop orphan partial index
    op.drop_index("ix_campaign_legs_orphaned", table_name="campaign_legs")

    # Restore trade_evaluations FK to CASCADE
    op.drop_constraint(
        "trade_evaluations_campaign_id_fkey",
        "trade_evaluations",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "trade_evaluations_campaign_id_fkey",
        "trade_evaluations",
        "position_campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Restore decision_contexts FK to CASCADE
    op.drop_constraint(
        "decision_contexts_campaign_id_fkey",
        "decision_contexts",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "decision_contexts_campaign_id_fkey",
        "decision_contexts",
        "position_campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Restore campaign_legs.campaign_id FK to CASCADE + NOT NULL
    op.drop_constraint(
        "campaign_legs_campaign_id_fkey", "campaign_legs", type_="foreignkey"
    )
    # Set any orphaned legs' campaign_id — must handle before making NOT NULL
    # In downgrade, orphaned legs without a campaign cannot survive.
    # Delete orphaned legs first.
    op.execute("DELETE FROM campaign_legs WHERE campaign_id IS NULL")
    op.alter_column(
        "campaign_legs",
        "campaign_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.create_foreign_key(
        "campaign_legs_campaign_id_fkey",
        "campaign_legs",
        "position_campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Drop check constraint
    op.drop_constraint("ck_leg_direction", "campaign_legs", type_="check")

    # Drop denormalized columns
    op.drop_column("campaign_legs", "account_id")
    op.drop_column("campaign_legs", "direction")
    op.drop_column("campaign_legs", "symbol")
