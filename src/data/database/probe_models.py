"""SQLAlchemy ORM models for strategy probe system.

Stores strategy definitions (catalog), aggregated probe results,
and detailed per-trade records with entry/exit justifications.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.database.models import Base


class ProbeStrategy(Base):
    """Strategy catalog for the probe system.

    Each row represents one of the 100 TA-Lib strategies with its
    metadata, philosophy, and structured entry/exit rules.
    """

    __tablename__ = "probe_strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    philosophy: Mapped[str] = mapped_column(String(500), nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(15), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
    )

    # Relationships
    probe_results: Mapped[list["StrategyProbeResult"]] = relationship(
        "StrategyProbeResult", back_populates="strategy", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ProbeStrategy(id={self.id}, name='{self.name}', type='{self.strategy_type}')>"


class StrategyProbeResult(Base):
    """Aggregated probe results grouped by dimensions.

    Each row holds aggregated trade metrics for a specific combination of
    (run_id, symbol, strategy, timeframe, risk_profile, open_day, open_hour, long_short).
    """

    __tablename__ = "strategy_probe_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    strategy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("probe_strategies.id", ondelete="CASCADE"), nullable=False,
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    strategy_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Dimensions
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    risk_profile: Mapped[str] = mapped_column(String(10), nullable=False)
    open_day: Mapped[date] = mapped_column(Date, nullable=False)
    open_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    long_short: Mapped[str] = mapped_column(String(5), nullable=False)

    # Aggregations
    num_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    pnl_mean: Mapped[float] = mapped_column(Float, nullable=False)
    pnl_std: Mapped[float] = mapped_column(Float, nullable=False)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False)
    max_profit: Mapped[float] = mapped_column(Float, nullable=False)

    # Optional metadata
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False,
    )

    # Relationships
    strategy: Mapped["ProbeStrategy"] = relationship("ProbeStrategy", back_populates="probe_results")
    trades: Mapped[list["ProbeStrategyTrade"]] = relationship(
        "ProbeStrategyTrade", back_populates="probe_result", cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "run_id", "symbol", "strategy_id", "timeframe", "risk_profile",
            "open_day", "open_hour", "long_short",
            name="uq_probe_result_dimensions",
        ),
        Index("ix_probe_strat_tf_risk", "strategy_id", "timeframe", "risk_profile"),
        Index("ix_probe_symbol_run", "symbol", "run_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<StrategyProbeResult(run_id='{self.run_id}', strategy_id={self.strategy_id}, "
            f"tf='{self.timeframe}', risk='{self.risk_profile}', trades={self.num_trades})>"
        )


class ProbeStrategyTrade(Base):
    """Individual trade record from a probe run.

    Each row represents one trade (entry + exit) with full context including
    human-readable justifications for why the trade was opened and closed.
    Links back to the aggregated result via strategy_probe_result_id FK.
    """

    __tablename__ = "strategy_probe_trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    strategy_probe_result_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("strategy_probe_results.id", ondelete="CASCADE"), nullable=False,
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    open_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    direction: Mapped[str] = mapped_column(String(5), nullable=False)  # "long" or "short"
    open_justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    close_justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    pnl: Mapped[float] = mapped_column(Float, nullable=False)
    pnl_pct: Mapped[float] = mapped_column(Float, nullable=False)
    bars_held: Mapped[int] = mapped_column(Integer, nullable=False)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_profit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    pnl_std: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False,
    )

    # Relationships
    probe_result: Mapped["StrategyProbeResult"] = relationship(
        "StrategyProbeResult", back_populates="trades",
    )

    __table_args__ = (
        Index("ix_probe_trades_result_id", "strategy_probe_result_id"),
        Index("ix_probe_trades_ticker", "ticker"),
        Index("ix_probe_trades_direction", "direction"),
        Index("ix_probe_trades_open_ts", "open_timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProbeStrategyTrade(id={self.id}, ticker='{self.ticker}', "
            f"direction='{self.direction}', pnl_pct={self.pnl_pct:.4f})>"
        )
