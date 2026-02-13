"""Add campaign_checks table for behavioral nudges.

Stores per-leg check evaluations (risk sanity, overtrading, revenge
trading, etc.) with severity, pass/fail, trader acknowledgement, and
action taken. Checks live at the leg level so moving legs between
campaigns automatically carries their checks.

Revision ID: 019
Revises: 018
Create Date: 2026-02-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaign_checks",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "leg_id",
            sa.BigInteger,
            sa.ForeignKey("campaign_legs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "account_id",
            sa.Integer,
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("check_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("nudge_text", sa.Text, nullable=True),
        sa.Column("acknowledged", sa.Boolean, nullable=True),
        sa.Column("trader_action", sa.String(20), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("check_phase", sa.String(20), nullable=False),
        # Check constraints
        sa.CheckConstraint(
            "severity IN ('info', 'warn', 'block', 'danger')",
            name="ck_check_severity",
        ),
        sa.CheckConstraint(
            "check_phase IN ('pre_trade', 'at_entry', 'during', 'at_exit', 'post_trade')",
            name="ck_check_phase",
        ),
        sa.CheckConstraint(
            "trader_action IS NULL OR trader_action IN ('proceeded', 'modified', 'cancelled')",
            name="ck_check_trader_action",
        ),
    )

    op.create_index(
        "ix_campaign_checks_account_check_type",
        "campaign_checks",
        ["account_id", "check_type"],
    )
    op.create_index(
        "ix_campaign_checks_account_checked_at",
        "campaign_checks",
        ["account_id", "checked_at"],
    )


def downgrade() -> None:
    op.drop_table("campaign_checks")
