"""Make campaign_checks.decision_context_id NOT NULL.

Every check must belong to a decision context. Deletes orphaned checks
(created during migration transition) that have null decision_context_id,
then enforces the constraint.

Revision ID: 028
Revises: 027
Create Date: 2026-02-16
"""

from alembic import op

# revision identifiers
revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Delete orphaned checks with no decision context
    op.execute("DELETE FROM campaign_checks WHERE decision_context_id IS NULL")

    # Make decision_context_id NOT NULL
    op.alter_column(
        "campaign_checks",
        "decision_context_id",
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "campaign_checks",
        "decision_context_id",
        nullable=True,
    )
