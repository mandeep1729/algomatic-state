"""Create waitlist table for user access gating.

Stores users who want access to the platform. Status values:
- waiting: submitted interest, pending manual approval
- approved: approved for account creation
- rejected: denied access

Approval is manual (direct DB update) — no admin UI yet.

Revision ID: 028
Revises: 027
Create Date: 2026-02-16
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "waitlist",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="waiting",
        ),
        sa.Column("referral_source", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('waiting', 'approved', 'rejected')",
            name="ck_waitlist_status",
        ),
        sa.Index("ix_waitlist_email", "email"),
        sa.Index("ix_waitlist_status", "status"),
    )


def downgrade() -> None:
    op.drop_table("waitlist")
