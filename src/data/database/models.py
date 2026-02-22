"""SQLAlchemy ORM models for market data storage."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


from sqlalchemy.dialects.postgresql import JSONB


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Ticker(Base):
    """Ticker/symbol metadata table.

    Stores information about tradeable symbols (stocks, ETFs, etc.).
    """

    __tablename__ = "tickers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    exchange: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(20), default="stock", nullable=False)
    asset_class: Mapped[str] = mapped_column(String(20), default="stock", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    bars: Mapped[list["OHLCVBar"]] = relationship(
        "OHLCVBar",
        back_populates="ticker",
        cascade="all, delete-orphan",
    )
    sync_logs: Mapped[list["DataSyncLog"]] = relationship(
        "DataSyncLog",
        back_populates="ticker",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Ticker(id={self.id}, symbol='{self.symbol}')>"


class OHLCVBar(Base):
    """OHLCV (Open, High, Low, Close, Volume) bar data.

    Stores price and volume data for a specific symbol and timeframe.
    Supports multiple timeframes: 1Min, 5Min, 15Min, 1Hour, 1Day.

    Note: composite PK (id, timestamp) is required by TimescaleDB hypertable
    partitioning — the partition column must be part of the primary key.
    """

    __tablename__ = "ohlcv_bars"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticker_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tickers.id", ondelete="CASCADE"),
        nullable=False,
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    trade_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="alpaca")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    ticker: Mapped["Ticker"] = relationship("Ticker", back_populates="bars")

    # Table constraints
    __table_args__ = (
        # Unique constraint on ticker + timeframe + timestamp
        UniqueConstraint("ticker_id", "timeframe", "timestamp", name="uq_bar_ticker_timeframe_ts"),
        # Performance index for common query pattern
        Index("ix_ohlcv_ticker_timeframe_ts", "ticker_id", "timeframe", "timestamp", postgresql_using="btree"),
        # Index for timestamp-based queries
        Index("ix_ohlcv_timestamp", "timestamp", postgresql_using="btree"),
        # Data integrity constraints
        CheckConstraint("high >= low", name="ck_high_gte_low"),
        CheckConstraint("high >= open AND high >= close", name="ck_high_gte_open_close"),
        CheckConstraint("low <= open AND low <= close", name="ck_low_lte_open_close"),
        CheckConstraint("open > 0", name="ck_positive_open"),
        CheckConstraint("high > 0", name="ck_positive_high"),
        CheckConstraint("low > 0", name="ck_positive_low"),
        CheckConstraint("close > 0", name="ck_positive_close"),
        CheckConstraint("volume >= 0", name="ck_non_negative_volume"),
    )

    def __repr__(self) -> str:
        return (
            f"<OHLCVBar(ticker_id={self.ticker_id}, timeframe='{self.timeframe}', "
            f"timestamp={self.timestamp}, close={self.close})>"
        )


class ComputedFeature(Base):
    """Computed features for OHLCV bars.

    Stores derived Technical Indicators and other features in a JSONB column
    for flexibility.
    """

    __tablename__ = "computed_features"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bar_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        unique=True,
    )
    ticker_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tickers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    
    # Feature storage: {"rsi_14": 45.3, "sma_200": 150.2, ...}
    features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    feature_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # HMM state columns (consolidated from ohlcv_states table)
    model_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    state_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # -1 indicates OOD
    state_prob: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    log_likelihood: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    ticker: Mapped["Ticker"] = relationship("Ticker")

    # Constraints
    __table_args__ = (
        # Ensure we don't duplicate features for same bar (covered by unique bar_id, but good to be explicit about logical unique)
        Index("ix_features_ticker_timeframe_ts", "ticker_id", "timeframe", "timestamp"),
        # Index for state queries
        Index("ix_features_model_state", "model_id", "state_id"),
        # State probability must be between 0 and 1 (when set)
        CheckConstraint("state_prob IS NULL OR (state_prob >= 0 AND state_prob <= 1)", name="ck_state_prob_range"),
    )

    def __repr__(self) -> str:
        return f"<ComputedFeature(ticker_id={self.ticker_id}, ts={self.timestamp})>"


class DataSyncLog(Base):
    """Track data synchronization status for each ticker/timeframe.

    Used to implement smart incremental fetching - only fetch data
    after the last synced timestamp.
    """

    __tablename__ = "data_sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tickers.id", ondelete="CASCADE"),
        nullable=False,
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    last_synced_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    first_synced_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_sync_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    bars_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_bars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    ticker: Mapped["Ticker"] = relationship("Ticker", back_populates="sync_logs")

    # Table constraints
    __table_args__ = (
        UniqueConstraint("ticker_id", "timeframe", name="uq_sync_ticker_timeframe"),
        Index("ix_sync_ticker_timeframe", "ticker_id", "timeframe"),
    )

    def __repr__(self) -> str:
        return (
            f"<DataSyncLog(ticker_id={self.ticker_id}, timeframe='{self.timeframe}', "
            f"last_synced={self.last_synced_timestamp}, status='{self.status}')>"
        )


# Valid timeframes
VALID_TIMEFRAMES = frozenset({"1Min", "5Min", "15Min", "1Hour", "1Day"})

# Valid data sources
VALID_SOURCES = frozenset({"alpaca", "finnhub", "csv_import", "manual", "aggregated"})
