"""Remove 'danger' severity from campaign_checks constraint.

Simplifies severity scale to: info, warn, critical.
Migrates any existing 'danger' rows to 'critical'.

Revision ID: 025
Revises: 024
Create Date: 2026-02-14
"""

from alembic import op

# revision identifiers
revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_check_severity", "campaign_checks", type_="check")

    # Migrate any existing 'danger' rows to 'critical'
    op.execute("UPDATE campaign_checks SET severity = 'critical' WHERE severity = 'danger'")

    # Recreate constraint without 'danger'
    op.create_check_constraint(
        "ck_check_severity",
        "campaign_checks",
        "severity IN ('info', 'warn', 'critical')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_check_severity", "campaign_checks", type_="check")

    # Restore 'danger' in the allowed values
    op.create_check_constraint(
        "ck_check_severity",
        "campaign_checks",
        "severity IN ('info', 'warn', 'critical', 'danger')",
    )
