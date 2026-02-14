"""SQLAlchemy ORM models for trade lifecycle tracking.

Defines tables for:
- PositionLot: Open position inventory and cost basis.
- LotClosure: Pairing of open fills with closing fills.
- PositionCampaign: User-visible trade journey (flat→flat).
- CampaignLeg: Semantic decision points within a campaign.
- LegFillMap: Join table mapping legs to fills.
- DecisionContext: Trader's context/feelings at decision points.
- CampaignCheck: Behavioral nudge checks attached to campaign legs.
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

    strategy_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("strategies.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(10), default="open", nullable=False, index=True)

    # Link to parent campaign
    campaign_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("position_campaigns.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    account: Mapped["UserAccount"] = relationship("UserAccount")
    open_fill: Mapped["TradeFill"] = relationship("TradeFill")
    campaign: Mapped[Optional["PositionCampaign"]] = relationship("PositionCampaign")
    strategy: Mapped[Optional["Strategy"]] = relationship("Strategy")
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


class PositionCampaign(Base):
    """User-visible trade journey from flat → flat.

    Represents a complete position lifecycle. Evolved from round_trips,
    this is the central object users interact with in the UI. Campaigns
    contain legs (decision points) and link to evaluations and contexts.
    """

    __tablename__ = "position_campaigns"

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

    # Traceability: lot_ids, closure_ids used to derive this campaign
    derived_from: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # --- New columns for campaign support ---
    status: Mapped[str] = mapped_column(String(10), default="open", nullable=False)
    max_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cost_basis_method: Mapped[str] = mapped_column(String(10), default="average", nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="broker_synced", nullable=False)
    link_group_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    r_multiple: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    intent_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("trade_intents.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=True,
    )

    # Relationships
    account: Mapped["UserAccount"] = relationship("UserAccount")
    intent: Mapped[Optional["TradeIntent"]] = relationship("TradeIntent")
    legs: Mapped[list["CampaignLeg"]] = relationship(
        "CampaignLeg",
        back_populates="campaign",
        cascade="all",
        order_by="CampaignLeg.started_at",
    )

    __table_args__ = (
        CheckConstraint("direction IN ('long', 'short')", name="ck_campaign_direction"),
        CheckConstraint("status IN ('open', 'closed')", name="ck_campaign_status"),
        CheckConstraint(
            "cost_basis_method IN ('average', 'fifo', 'lifo')",
            name="ck_campaign_cost_basis",
        ),
        CheckConstraint(
            "source IN ('broker_synced', 'manual', 'proposed')",
            name="ck_campaign_source",
        ),
        Index("ix_position_campaigns_account_symbol", "account_id", "symbol"),
        Index("ix_position_campaigns_account_closed", "account_id", "closed_at"),
        Index("ix_position_campaigns_account_status", "account_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<PositionCampaign(id={self.id}, symbol='{self.symbol}', "
            f"direction='{self.direction}', status='{self.status}', pnl={self.realized_pnl})>"
        )


class CampaignLeg(Base):
    """A leg groups one or more trade fills that share the same intent.

    Each leg represents a semantic decision point within a campaign
    (open, add, reduce, close). Legs are the primary unit of evaluation.
    """

    __tablename__ = "campaign_legs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    campaign_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("position_campaigns.id", ondelete="SET NULL"),
        nullable=True,
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # 'long', 'short'
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    leg_type: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # 'buy', 'sell'
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    avg_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    fill_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    intent_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("trade_intents.id", ondelete="SET NULL"),
        nullable=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    campaign: Mapped[Optional["PositionCampaign"]] = relationship("PositionCampaign", back_populates="legs")
    account: Mapped["UserAccount"] = relationship("UserAccount")
    intent: Mapped[Optional["TradeIntent"]] = relationship("TradeIntent")
    fill_maps: Mapped[list["LegFillMap"]] = relationship(
        "LegFillMap",
        back_populates="leg",
        cascade="all, delete-orphan",
    )
    checks: Mapped[list["CampaignCheck"]] = relationship(
        "CampaignCheck",
        back_populates="leg",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "leg_type IN ('open', 'add', 'reduce', 'close', 'flip_close', 'flip_open')",
            name="ck_leg_type",
        ),
        CheckConstraint("side IN ('buy', 'sell')", name="ck_leg_side"),
        CheckConstraint("quantity > 0", name="ck_leg_qty_positive"),
        CheckConstraint("direction IN ('long', 'short')", name="ck_leg_direction"),
        Index("ix_campaign_legs_campaign_started", "campaign_id", "started_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<CampaignLeg(id={self.id}, campaign_id={self.campaign_id}, "
            f"type='{self.leg_type}', side='{self.side}', qty={self.quantity})>"
        )


class LegFillMap(Base):
    """Join table mapping campaign legs to trade fills.

    Supports partial allocation when a single fill contributes
    to multiple legs (e.g., a large fill that closes one campaign
    and opens another).
    """

    __tablename__ = "leg_fill_map"

    leg_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("campaign_legs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    fill_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("trade_fills.id", ondelete="CASCADE"),
        primary_key=True,
    )
    allocated_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    leg: Mapped["CampaignLeg"] = relationship("CampaignLeg", back_populates="fill_maps")
    fill: Mapped["TradeFill"] = relationship("TradeFill")

    def __repr__(self) -> str:
        return f"<LegFillMap(leg_id={self.leg_id}, fill_id={self.fill_id}, qty={self.allocated_qty})>"


class DecisionContext(Base):
    """Trader's context and feelings at a decision point.

    Captures the qualitative aspects of trading decisions:
    strategy tags, hypothesis, exit intent, and emotional state.
    Can be attached to a campaign, leg, or intent.
    """

    __tablename__ = "decision_contexts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Polymorphic links (at least one should be set)
    campaign_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("position_campaigns.id", ondelete="SET NULL"),
        nullable=True,
    )
    leg_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("campaign_legs.id", ondelete="CASCADE"),
        nullable=True,
    )
    intent_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("trade_intents.id", ondelete="SET NULL"),
        nullable=True,
    )

    context_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # Strategy reference (replaces free-text strategy_tags)
    strategy_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("strategies.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Behavioral metadata
    hypothesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_intent: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    feelings_then: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    feelings_now: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
    account: Mapped["UserAccount"] = relationship("UserAccount")
    campaign: Mapped[Optional["PositionCampaign"]] = relationship("PositionCampaign")
    leg: Mapped[Optional["CampaignLeg"]] = relationship("CampaignLeg")
    intent: Mapped[Optional["TradeIntent"]] = relationship("TradeIntent")
    strategy: Mapped[Optional["Strategy"]] = relationship("Strategy")

    __table_args__ = (
        CheckConstraint(
            "context_type IN ('entry', 'add', 'reduce', 'exit', 'idea', 'post_trade_reflection')",
            name="ck_context_type",
        ),
        Index("ix_decision_contexts_account_campaign", "account_id", "campaign_id"),
        Index("ix_decision_contexts_account_created", "account_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<DecisionContext(id={self.id}, type='{self.context_type}', "
            f"campaign_id={self.campaign_id}, leg_id={self.leg_id})>"
        )


class CampaignCheck(Base):
    """Behavioral nudge check attached to a campaign leg.

    Each row records one check evaluation (e.g. risk sanity, overtrading,
    revenge trading). Checks live at the leg level so that moving legs
    between campaigns automatically moves their checks.

    Traders can acknowledge checks and record what action they took.
    """

    __tablename__ = "campaign_checks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    leg_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("campaign_legs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    check_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    nudge_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    acknowledged: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    trader_action: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    check_phase: Mapped[str] = mapped_column(String(20), nullable=False)

    # Relationships
    leg: Mapped["CampaignLeg"] = relationship("CampaignLeg", back_populates="checks")
    account: Mapped["UserAccount"] = relationship("UserAccount")

    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'warn', 'block', 'danger')",
            name="ck_check_severity",
        ),
        CheckConstraint(
            "check_phase IN ('pre_trade', 'at_entry', 'during', 'at_exit', 'post_trade')",
            name="ck_check_phase",
        ),
        CheckConstraint(
            "trader_action IS NULL OR trader_action IN ('proceeded', 'modified', 'cancelled')",
            name="ck_check_trader_action",
        ),
        Index("ix_campaign_checks_account_check_type", "account_id", "check_type"),
        Index("ix_campaign_checks_account_checked_at", "account_id", "checked_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<CampaignCheck(id={self.id}, leg_id={self.leg_id}, "
            f"type='{self.check_type}', severity='{self.severity}', passed={self.passed})>"
        )
