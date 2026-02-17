"""Add implied_strategy_family column to strategies table.

Stores the detected strategy theme family (e.g., trend, breakout, momentum).
This field is auto-populated by the application (never set by user directly)
and used to infer strategy family when user-defined strategy name matches
a theme.

Revision ID: 029
Revises: 028
Create Date: 2026-02-16
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "strategies",
        sa.Column("implied_strategy_family", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("strategies", "implied_strategy_family")
