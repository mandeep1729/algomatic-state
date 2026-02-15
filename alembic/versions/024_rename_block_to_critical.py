"""Rename severity 'block' to 'critical' in campaign_checks.

Updates the check constraint and migrates existing data.

Revision ID: 024
Revises: 023
Create Date: 2026-02-14
"""

from alembic import op

# revision identifiers
revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop constraint first so data update is allowed
    op.drop_constraint("ck_check_severity", "campaign_checks", type_="check")

    # Update existing rows
    op.execute("UPDATE campaign_checks SET severity = 'critical' WHERE severity = 'block'")

    # Recreate constraint with new values
    op.create_check_constraint(
        "ck_check_severity",
        "campaign_checks",
        "severity IN ('info', 'warn', 'critical', 'danger')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_check_severity", "campaign_checks", type_="check")

    op.execute("UPDATE campaign_checks SET severity = 'block' WHERE severity = 'critical'")

    op.create_check_constraint(
        "ck_check_severity",
        "campaign_checks",
        "severity IN ('info', 'warn', 'block', 'danger')",
    )
