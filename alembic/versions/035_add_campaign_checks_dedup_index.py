"""Add campaign_checks dedup composite index.

Adds a composite index on (account_id, decision_context_id, check_name)
to support efficient deduplication lookups in the reviewer-service.

Revision ID: 035
Revises: 034
Create Date: 2026-02-17
"""

from alembic import op

# revision identifiers
revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_campaign_checks_dedup",
        "campaign_checks",
        ["account_id", "decision_context_id", "check_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_campaign_checks_dedup", table_name="campaign_checks")
