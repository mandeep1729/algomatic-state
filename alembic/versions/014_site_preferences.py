"""Add site_prefs JSONB column to user_profiles.

Stores UI/site-level preferences (theme, sidebar state, notification
settings, language) separate from trading profile and risk settings.

Revision ID: 014
Revises: 013
Create Date: 2026-02-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("site_prefs", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "site_prefs")
