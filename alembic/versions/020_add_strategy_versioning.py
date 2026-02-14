"""Add strategy versioning columns.

Adds a `version` column to `probe_strategies` and a `strategy_version`
column to `strategy_probe_results` so that result rows can be traced
back to the exact strategy definition revision that produced them.

Revision ID: 020
Revises: 019
Create Date: 2026-02-13
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "probe_strategies",
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.add_column(
        "strategy_probe_results",
        sa.Column("strategy_version", sa.Integer, nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("strategy_probe_results", "strategy_version")
    op.drop_column("probe_strategies", "version")
