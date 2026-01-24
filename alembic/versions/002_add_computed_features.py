"""Add computed_features table.

Revision ID: 002
Revises: 001
Create Date: 2024-01-23 00:00:00.000000

Creates the following tables:
- computed_features: Flexible JSONB storage for calculated indicators
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create computed_features table."""
    op.create_table(
        "computed_features",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("bar_id", sa.BigInteger(), nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("features", JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("feature_version", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["bar_id"], ["ohlcv_bars.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticker_id"], ["tickers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bar_id", name="uq_features_bar_id"),
    )
    
    # Create performance index for querying features by ticker/timeframe/time
    op.create_index(
        "ix_features_ticker_timeframe_ts",
        "computed_features",
        ["ticker_id", "timeframe", "timestamp"],
    )


def downgrade() -> None:
    """Drop computed_features table."""
    op.drop_table("computed_features")
