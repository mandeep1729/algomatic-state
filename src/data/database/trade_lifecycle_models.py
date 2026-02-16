"""SQLAlchemy ORM models for trade lifecycle tracking.

Defines tables for:
- DecisionContext: Trader's context/feelings attached 1-to-1 with a fill.
- CampaignCheck: Behavioral nudge checks attached to decision contexts.
- Campaign: Derived campaign grouping (flat-to-flat).
- CampaignFill: Junction table linking campaigns to fills.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
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


class DecisionContext(Base):
    """Trader's context and feelings attached 1-to-1 with a trade fill.

    Captures the qualitative aspects of trading decisions:
    strategy tags, hypothesis, exit intent, and emotional state.
    """

    __tablename__ = "decision_contexts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Strict 1-to-1 with trade_fills
    fill_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("trade_fills.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    context_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # Strategy reference
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
    fill: Mapped["TradeFill"] = relationship(
        "TradeFill", back_populates="decision_context"
    )
    strategy: Mapped[Optional["Strategy"]] = relationship("Strategy")
    checks: Mapped[list["CampaignCheck"]] = relationship(
        "CampaignCheck",
        back_populates="decision_context",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "context_type IN ('entry', 'add', 'reduce', 'exit', 'idea', 'post_trade_reflection')",
            name="ck_context_type",
        ),
        Index("ix_decision_contexts_account_fill", "account_id", "fill_id"),
        Index("ix_decision_contexts_account_created", "account_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<DecisionContext(id={self.id}, type='{self.context_type}', "
            f"fill_id={self.fill_id})>"
        )


class CampaignCheck(Base):
    """Behavioral nudge check attached to a decision context.

    Each row records one check evaluation (e.g. risk sanity, overtrading,
    revenge trading). Checks live at the decision context level.

    Traders can acknowledge checks and record what action they took.
    """

    __tablename__ = "campaign_checks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    decision_context_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("decision_contexts.id", ondelete="CASCADE"),
        nullable=True,
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
    decision_context: Mapped[Optional["DecisionContext"]] = relationship(
        "DecisionContext", back_populates="checks"
    )
    account: Mapped["UserAccount"] = relationship("UserAccount")

    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'warn', 'critical')",
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
        Index("ix_campaign_checks_decision_context", "decision_context_id"),
        Index("ix_campaign_checks_account_check_type", "account_id", "check_type"),
        Index("ix_campaign_checks_account_checked_at", "account_id", "checked_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<CampaignCheck(id={self.id}, dc_id={self.decision_context_id}, "
            f"type='{self.check_type}', severity='{self.severity}', passed={self.passed})>"
        )


class Campaign(Base):
    """Derived campaign grouping — a flat-to-flat trade journey.

    Campaigns are computed from fills + decision_contexts. They are
    cheap derived data: delete and rebuild is the update strategy.
    """

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    strategy_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("strategies.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    account: Mapped["UserAccount"] = relationship("UserAccount")
    strategy: Mapped[Optional["Strategy"]] = relationship("Strategy")
    campaign_fills: Mapped[list["CampaignFill"]] = relationship(
        "CampaignFill",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_campaigns_account_symbol_strategy", "account_id", "symbol", "strategy_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Campaign(id={self.id}, symbol='{self.symbol}', "
            f"strategy_id={self.strategy_id})>"
        )


class CampaignFill(Base):
    """Junction table linking campaigns to trade fills."""

    __tablename__ = "campaign_fills"

    campaign_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        primary_key=True,
    )
    fill_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("trade_fills.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="campaign_fills")
    fill: Mapped["TradeFill"] = relationship("TradeFill")

    def __repr__(self) -> str:
        return f"<CampaignFill(campaign_id={self.campaign_id}, fill_id={self.fill_id})>"
