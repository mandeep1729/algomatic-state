"""Add tags column to trade_fills for broker strategy tracking.

Adds a tags column (JSONB) to store broker-provided metadata like strategy_id,
allowing fills to be linked back to the strategy that generated them.

Revision ID: 037
Revises: 036
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trade_fills",
        sa.Column("tags", sa.dialects.postgresql.JSONB, nullable=True, default={}, server_default=sa.func.jsonb_build_object()),
    )


def downgrade() -> None:
    op.drop_column("trade_fills", "tags")
