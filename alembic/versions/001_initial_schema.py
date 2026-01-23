"""Initial schema for market data storage.

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

Creates the following tables:
- tickers: Symbol metadata
- ohlcv_bars: OHLCV price/volume data
- data_sync_log: Data synchronization tracking
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial tables."""

    # Create tickers table
    op.create_table(
        "tickers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("exchange", sa.String(length=50), nullable=True),
        sa.Column("asset_type", sa.String(length=20), nullable=False, server_default="stock"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol"),
    )
    op.create_index("ix_tickers_symbol", "tickers", ["symbol"], unique=True)

    # Create ohlcv_bars table
    op.create_table(
        "ohlcv_bars",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("vwap", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="alpaca"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["ticker_id"], ["tickers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # Uniqueness constraint
        sa.UniqueConstraint("ticker_id", "timeframe", "timestamp", name="uq_bar_ticker_timeframe_ts"),
        # Data integrity constraints
        sa.CheckConstraint("high >= low", name="ck_high_gte_low"),
        sa.CheckConstraint("high >= open AND high >= close", name="ck_high_gte_open_close"),
        sa.CheckConstraint("low <= open AND low <= close", name="ck_low_lte_open_close"),
        sa.CheckConstraint("open > 0", name="ck_positive_open"),
        sa.CheckConstraint("high > 0", name="ck_positive_high"),
        sa.CheckConstraint("low > 0", name="ck_positive_low"),
        sa.CheckConstraint("close > 0", name="ck_positive_close"),
        sa.CheckConstraint("volume >= 0", name="ck_non_negative_volume"),
    )
    # Performance indexes
    op.create_index(
        "ix_ohlcv_ticker_timeframe_ts",
        "ohlcv_bars",
        ["ticker_id", "timeframe", "timestamp"],
    )
    op.create_index("ix_ohlcv_timestamp", "ohlcv_bars", ["timestamp"])

    # Create data_sync_log table
    op.create_table(
        "data_sync_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("last_synced_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_synced_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_sync_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("bars_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_bars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["ticker_id"], ["tickers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker_id", "timeframe", name="uq_sync_ticker_timeframe"),
    )
    op.create_index("ix_sync_ticker_timeframe", "data_sync_log", ["ticker_id", "timeframe"])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("data_sync_log")
    op.drop_table("ohlcv_bars")
    op.drop_table("tickers")
