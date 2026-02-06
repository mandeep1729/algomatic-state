"""SQLAlchemy ORM models for trade lifecycle tracking.

Defines tables for:
- PositionLot: Open position inventory and cost basis.
- LotClosure: Pairing of open fills with closing fills.
- RoundTrip: Derived user-visible "trade" for analytics and UI.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.database.models import Base


class PositionLot(Base):
    """Open position lot representing inventory and cost basis.

    One row per opened lot, created from an opening fill.
    remaining_qty decreases as the lot is closed via LotClosure entries.
    """

    __tablename__ = "position_lots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # 'long', 'short'

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open_fill_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("trade_fills.id", ondelete="CASCADE"),
        nullable=False,
    )

    open_qty: Mapped[float] = mapped_column(Float, nullable=False)
    remaining_qty: Mapped[float] = mapped_column(Float, nullable=False)
    avg_open_price: Mapped[float] = mapped_column(Float, nullable=False)

    strategy_tag: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="open", nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    account: Mapped["UserAccount"] = relationship("UserAccount")
    open_fill: Mapped["TradeFill"] = relationship("TradeFill")
    closures: Mapped[list["LotClosure"]] = relationship(
        "LotClosure",
        back_populates="lot",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("direction IN ('long', 'short')", name="ck_lot_direction"),
        CheckConstraint("open_qty > 0", name="ck_lot_open_qty_positive"),
        CheckConstraint("remaining_qty >= 0", name="ck_lot_remaining_qty_nonneg"),
        CheckConstraint("avg_open_price > 0", name="ck_lot_avg_price_positive"),
        CheckConstraint("status IN ('open', 'closed')", name="ck_lot_status"),
        Index("ix_position_lots_account_symbol_status", "account_id", "symbol", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<PositionLot(id={self.id}, symbol='{self.symbol}', "
            f"direction='{self.direction}', remaining={self.remaining_qty})>"
        )


class LotClosure(Base):
    """Pairing of an open lot with a closing fill.

    Each row represents a partial or full match between one open lot
    and one closing fill for a specific quantity. This solves the
    pairing problem for partial closes, scale in/out, and shorts.
    """

    __tablename__ = "lot_closures"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("position_lots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    open_fill_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("trade_fills.id", ondelete="CASCADE"),
        nullable=False,
    )
    close_fill_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("trade_fills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    matched_qty: Mapped[float] = mapped_column(Float, nullable=False)
    open_price: Mapped[float] = mapped_column(Float, nullable=False)
    close_price: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fees_allocated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    match_method: Mapped[str] = mapped_column(String(10), default="fifo", nullable=False)

    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    lot: Mapped["PositionLot"] = relationship("PositionLot", back_populates="closures")
    open_fill: Mapped["TradeFill"] = relationship("TradeFill", foreign_keys=[open_fill_id])
    close_fill: Mapped["TradeFill"] = relationship("TradeFill", foreign_keys=[close_fill_id])

    __table_args__ = (
        CheckConstraint("matched_qty > 0", name="ck_closure_qty_positive"),
        CheckConstraint("open_price > 0", name="ck_closure_open_price_positive"),
        CheckConstraint("close_price > 0", name="ck_closure_close_price_positive"),
        CheckConstraint(
            "match_method IN ('fifo', 'lifo', 'avg', 'manual')",
            name="ck_closure_match_method",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<LotClosure(id={self.id}, lot_id={self.lot_id}, "
            f"qty={self.matched_qty}, pnl={self.realized_pnl})>"
        )


class RoundTrip(Base):
    """Derived user-visible "trade" for analytics and UI.

    Represents a complete open→close cycle. This is derived from lots
    and closures, not canonical. Can be rebuilt anytime from underlying data.
    """

    __tablename__ = "round_trips"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # 'long', 'short'

    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    qty_opened: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    qty_closed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_open_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_close_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    realized_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    return_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    holding_period_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    num_fills: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Flexible metadata: strategy tags, labels, annotations
    tags: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Traceability: lot_ids, closure_ids used to derive this round trip
    derived_from: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    account: Mapped["UserAccount"] = relationship("UserAccount")

    __table_args__ = (
        CheckConstraint("direction IN ('long', 'short')", name="ck_rt_direction"),
        Index("ix_round_trips_account_symbol", "account_id", "symbol"),
        Index("ix_round_trips_account_closed", "account_id", "closed_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<RoundTrip(id={self.id}, symbol='{self.symbol}', "
            f"direction='{self.direction}', pnl={self.realized_pnl})>"
        )
