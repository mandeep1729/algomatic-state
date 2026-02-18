"""SQLAlchemy ORM models for automated trading agents.

Defines tables for:
- AgentStrategy: Strategy definitions (predefined + custom).
- TradingAgent: Agent instances that execute strategies.
- AgentOrder: Orders placed by agents.
- AgentActivityLog: Audit trail for agent actions.
"""

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.database.models import Base


class AgentStrategy(Base):
    """Strategy definition for automated trading agents.

    Predefined strategies reference go-strats IDs directly.
    Custom strategies store entry/exit conditions as JSONB.
    """

    __tablename__ = "agent_strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False, default="long_short")

    # Entry/exit conditions (JSONB arrays, empty for predefined strategies)
    entry_long: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    entry_short: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    exit_long: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    exit_short: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ATR-based exit parameters
    atr_stop_mult: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    atr_target_mult: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trailing_atr_mult: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_stop_bars: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Required indicator column names
    required_features: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Predefined strategy metadata
    is_predefined: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_strategy_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cloned_from_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("agent_strategies.id", ondelete="SET NULL"),
        nullable=True,
    )

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
    agents: Mapped[list["TradingAgent"]] = relationship(
        "TradingAgent", back_populates="strategy"
    )
    cloned_from: Mapped[Optional["AgentStrategy"]] = relationship(
        "AgentStrategy", remote_side=[id]
    )

    __table_args__ = (
        CheckConstraint(
            "category IN ('trend', 'mean_reversion', 'breakout', 'volume_flow', 'pattern', 'regime', 'custom')",
            name="ck_agent_strategy_category",
        ),
        CheckConstraint(
            "direction IN ('long_short', 'long_only', 'short_only')",
            name="ck_agent_strategy_direction",
        ),
        UniqueConstraint("account_id", "name", name="uq_agent_strategy_account_name"),
        Index("ix_agent_strategies_account_id", "account_id"),
        Index("ix_agent_strategies_category", "category"),
        Index("ix_agent_strategies_is_predefined", "is_predefined"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentStrategy(id={self.id}, name='{self.name}', "
            f"category='{self.category}', predefined={self.is_predefined})>"
        )


class TradingAgent(Base):
    """Agent instance that executes a strategy on a specific symbol.

    The Go agent-service polls for active agents and runs their trading loops.
    """

    __tablename__ = "trading_agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    strategy_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agent_strategies.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Status lifecycle: created -> active -> paused -> stopped | error
    status: Mapped[str] = mapped_column(String(20), default="created", nullable=False)

    # Trading parameters
    timeframe: Mapped[str] = mapped_column(String(10), default="5Min", nullable=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    lookback_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    position_size_dollars: Mapped[float] = mapped_column(Float, default=1000.0, nullable=False)

    # Risk and exit configuration overrides
    risk_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    exit_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Paper trading flag
    paper: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Runtime state (updated by Go agent-service)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_signal: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    consecutive_errors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_position: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

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
    strategy: Mapped["AgentStrategy"] = relationship(
        "AgentStrategy", back_populates="agents"
    )
    orders: Mapped[list["AgentOrder"]] = relationship(
        "AgentOrder", back_populates="agent", cascade="all, delete-orphan"
    )
    activity_logs: Mapped[list["AgentActivityLog"]] = relationship(
        "AgentActivityLog", back_populates="agent", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'active', 'paused', 'stopped', 'error')",
            name="ck_trading_agent_status",
        ),
        CheckConstraint(
            "timeframe IN ('1Min', '5Min', '15Min', '1Hour', '1Day')",
            name="ck_trading_agent_timeframe",
        ),
        UniqueConstraint("account_id", "name", name="uq_trading_agent_account_name"),
        Index("ix_trading_agents_account_id", "account_id"),
        Index("ix_trading_agents_status", "status"),
        Index("ix_trading_agents_account_status", "account_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<TradingAgent(id={self.id}, name='{self.name}', "
            f"symbol='{self.symbol}', status='{self.status}')>"
        )


class AgentOrder(Base):
    """Order placed by an automated trading agent."""

    __tablename__ = "agent_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("trading_agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Order details
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    order_type: Mapped[str] = mapped_column(String(20), default="market", nullable=False)
    limit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stop_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Broker identifiers
    client_order_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    broker_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    # Fill details
    filled_quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    filled_avg_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Signal metadata
    signal_direction: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    signal_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    risk_violations: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    filled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    agent: Mapped["TradingAgent"] = relationship(
        "TradingAgent", back_populates="orders"
    )

    __table_args__ = (
        CheckConstraint(
            "side IN ('buy', 'sell')",
            name="ck_agent_order_side",
        ),
        CheckConstraint(
            "status IN ('pending', 'submitted', 'accepted', 'filled', 'partially_filled', 'cancelled', 'rejected', 'expired')",
            name="ck_agent_order_status",
        ),
        Index("ix_agent_orders_agent_id", "agent_id"),
        Index("ix_agent_orders_account_id", "account_id"),
        Index("ix_agent_orders_agent_created", "agent_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentOrder(id={self.id}, agent_id={self.agent_id}, "
            f"symbol='{self.symbol}', side='{self.side}', status='{self.status}')>"
        )


class AgentActivityLog(Base):
    """Audit trail for agent actions and events."""

    __tablename__ = "agent_activity_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("trading_agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)

    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    severity: Mapped[str] = mapped_column(String(10), default="info", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    agent: Mapped["TradingAgent"] = relationship(
        "TradingAgent", back_populates="activity_logs"
    )

    __table_args__ = (
        CheckConstraint(
            "severity IN ('debug', 'info', 'warn', 'error')",
            name="ck_agent_activity_severity",
        ),
        Index("ix_agent_activity_agent_id", "agent_id"),
        Index("ix_agent_activity_agent_created", "agent_id", "created_at"),
        Index("ix_agent_activity_account_type", "account_id", "activity_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentActivityLog(id={self.id}, agent_id={self.agent_id}, "
            f"type='{self.activity_type}', severity='{self.severity}')>"
        )
