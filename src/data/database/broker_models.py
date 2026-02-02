"""SQLAlchemy ORM models for SnapTrade broker integration.

Defines tables for:
- SnapTradeUser: Mapping between internal user and SnapTrade user.
- BrokerConnection: Connected brokerage accounts.
- TradeHistory: Historical trades synced from brokers.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class SnapTradeUser(Base):
    """Mapping between internal user and SnapTrade user.
    
    Stores the user secret required for SnapTrade API calls on behalf of a user.
    """
    __tablename__ = "snaptrade_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    snaptrade_user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    snaptrade_user_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    user_account: Mapped["UserAccount"] = relationship("UserAccount")
    broker_connections: Mapped[list["BrokerConnection"]] = relationship(
        "BrokerConnection",
        back_populates="snaptrade_user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<SnapTradeUser(user_account_id={self.user_account_id}, snaptrade_id='{self.snaptrade_user_id}')>"


class BrokerConnection(Base):
    """Connected brokerage account via SnapTrade.
    
    Represents a single connection to a broker (e.g., "Robinhood", "Schwab").
    """
    __tablename__ = "broker_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snaptrade_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("snaptrade_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    brokerage_name: Mapped[str] = mapped_column(String(100), nullable=False)
    brokerage_slug: Mapped[str] = mapped_column(String(50), nullable=False)
    authorization_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    
    # Metadata for the connection (e.g., account numbers, status)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    
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
    snaptrade_user: Mapped["SnapTradeUser"] = relationship("SnapTradeUser", back_populates="broker_connections")
    trades: Mapped[list["TradeHistory"]] = relationship(
        "TradeHistory",
        back_populates="connection",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<BrokerConnection(brokerage='{self.brokerage_name}', auth_id='{self.authorization_id}')>"


class TradeHistory(Base):
    """Historical trade synced from a broker.
    
    Stores details of executed trades.
    """
    __tablename__ = "trade_histories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    broker_connection_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("broker_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # 'buy', 'sell'
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    fees: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    
    # External ID to prevent duplicates
    external_trade_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    
    # Raw data from provider
    raw_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    connection: Mapped["BrokerConnection"] = relationship("BrokerConnection", back_populates="trades")

    __table_args__ = (
        Index("ix_trade_histories_connection_symbol", "broker_connection_id", "symbol"),
    )

    def __repr__(self) -> str:
        return f"<TradeHistory(symbol='{self.symbol}', side='{self.side}', qty={self.quantity}, price={self.price})>"
