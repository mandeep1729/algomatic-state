"""Add check_name column to campaign_checks table.

Stores the unique check code (e.g. RS001, EQ001) as a top-level column
instead of relying on extraction from the JSONB details field.

Backfills existing rows from details->'code' or falls back to check_type.

Revision ID: 034
Revises: 033
Create Date: 2026-02-17
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add nullable column
    op.add_column(
        "campaign_checks",
        sa.Column("check_name", sa.String(50), nullable=True),
    )

    # Step 2: Backfill existing rows from details->code or check_type
    op.execute(
        """
        UPDATE campaign_checks
        SET check_name = COALESCE(details->>'code', check_type)
        """
    )

    # Step 3: Make non-nullable now that all rows have a value
    op.alter_column("campaign_checks", "check_name", nullable=False)

    # Step 4: Add index for lookups by check_name
    op.create_index(
        "ix_campaign_checks_check_name",
        "campaign_checks",
        ["check_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_campaign_checks_check_name", table_name="campaign_checks")
    op.drop_column("campaign_checks", "check_name")
