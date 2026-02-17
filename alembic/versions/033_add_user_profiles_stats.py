"""Add stats JSONB column to user_profiles table.

Stores aggregated trading statistics for the user profile.

Revision ID: 033
Revises: 032
Create Date: 2026-02-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("stats", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "stats")
