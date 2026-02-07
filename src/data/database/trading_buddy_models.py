"""SQLAlchemy ORM models for Trading Buddy platform.

Defines tables for:
- UserAccount: User account with auth and personal details
- UserProfile: Trading/risk preferences (1-to-1 with UserAccount)
- UserRule: Custom evaluation rules per user
- TradeIntent: User trade proposals
- TradeEvaluation: Evaluation results
- TradeEvaluationItem: Individual evaluation findings
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
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


class UserAccount(Base):
    """User account with auth and personal details.

    Stores authentication info and personal details.
    Trading/risk preferences live in UserProfile.
    """

    __tablename__ = "user_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_user_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Auth fields
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(50), default="google", nullable=False)
    profile_picture_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # Personal details
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Account status
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
    profile: Mapped[Optional["UserProfile"]] = relationship(
        "UserProfile",
        uselist=False,
        back_populates="account",
        cascade="all, delete-orphan",
    )
    rules: Mapped[list["UserRule"]] = relationship(
        "UserRule",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    trade_intents: Mapped[list["TradeIntent"]] = relationship(
        "TradeIntent",
        back_populates="account",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<UserAccount(id={self.id}, name='{self.name}')>"


class UserProfile(Base):
    """Trading and risk preferences for a user.

    One-to-one relationship with UserAccount. Stores risk parameters,
    trading style, and experience level.
    """

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Account balance and risk parameters
    account_balance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_position_size_pct: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    max_risk_per_trade_pct: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    max_daily_loss_pct: Mapped[float] = mapped_column(Float, default=3.0, nullable=False)
    min_risk_reward_ratio: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)

    # Default timeframes for analysis
    default_timeframes: Mapped[dict] = mapped_column(
        JSONB, default=lambda: ["1Min", "5Min", "15Min", "1Hour"], nullable=False
    )

    # Additional risk settings
    max_open_positions: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    stop_loss_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Trading profile
    experience_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    trading_style: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    primary_markets: Mapped[Optional[dict]] = mapped_column(
        JSONB, default=lambda: ["US_EQUITIES"], nullable=True
    )
    account_size_range: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Evaluation controls (JSONB for flexibility)
    evaluation_controls: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Timestamps
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
    account: Mapped["UserAccount"] = relationship("UserAccount", back_populates="profile")

    # Constraints
    __table_args__ = (
        CheckConstraint("account_balance >= 0", name="ck_profile_balance_positive"),
        CheckConstraint("max_position_size_pct > 0 AND max_position_size_pct <= 100", name="ck_profile_max_position_pct_range"),
        CheckConstraint("max_risk_per_trade_pct > 0 AND max_risk_per_trade_pct <= 100", name="ck_profile_max_risk_pct_range"),
        CheckConstraint("max_daily_loss_pct > 0 AND max_daily_loss_pct <= 100", name="ck_profile_max_daily_loss_range"),
        CheckConstraint("min_risk_reward_ratio > 0", name="ck_profile_min_rr_positive"),
    )

    def __repr__(self) -> str:
        return f"<UserProfile(id={self.id}, account_id={self.user_account_id})>"


class UserRule(Base):
    """Custom evaluation rule for a user.

    Allows users to define custom thresholds and rules
    that override defaults during evaluation.
    """

    __tablename__ = "user_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Rule identification
    rule_code: Mapped[str] = mapped_column(String(50), nullable=False)
    evaluator: Mapped[str] = mapped_column(String(100), nullable=False)

    # Rule parameters (flexible JSONB structure)
    # Example: {"threshold": 1.5, "severity": "warning"}
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Rule metadata
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    account: Mapped["UserAccount"] = relationship("UserAccount", back_populates="rules")

    # Constraints
    __table_args__ = (
        UniqueConstraint("account_id", "rule_code", name="uq_user_rule_account_code"),
        Index("ix_user_rules_evaluator", "evaluator"),
    )

    def __repr__(self) -> str:
        return f"<UserRule(id={self.id}, code='{self.rule_code}')>"


class TradeIntent(Base):
    """User's proposed trade for evaluation.

    Stores trade intent parameters and tracks status
    through the evaluation workflow.
    """

    __tablename__ = "trade_intents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Trade parameters
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # 'long' or 'short'
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g., '5Min', '1Hour'

    # Prices
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    profit_target: Mapped[float] = mapped_column(Float, nullable=False)

    # Position sizing
    position_size: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    position_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # User input
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hypothesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    strategy_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("strategies.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Workflow status
    status: Mapped[str] = mapped_column(
        String(30),
        default="draft",
        nullable=False,
        index=True,
    )

    # Additional context (flexible JSONB)
    intent_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Timestamps
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
    account: Mapped["UserAccount"] = relationship("UserAccount", back_populates="trade_intents")
    strategy: Mapped[Optional["Strategy"]] = relationship("Strategy")
    evaluation: Mapped[Optional["TradeEvaluation"]] = relationship(
        "TradeEvaluation",
        uselist=False,
        back_populates="intent",
        cascade="all, delete-orphan",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("direction IN ('long', 'short')", name="ck_intent_direction"),
        CheckConstraint("entry_price > 0", name="ck_intent_entry_positive"),
        CheckConstraint("stop_loss > 0", name="ck_intent_stop_positive"),
        CheckConstraint("profit_target > 0", name="ck_intent_target_positive"),
        CheckConstraint("position_size IS NULL OR position_size > 0", name="ck_intent_size_positive"),
        Index("ix_trade_intents_created", "created_at"),
        Index("ix_trade_intents_symbol_status", "symbol", "status"),
    )

    def __repr__(self) -> str:
        return f"<TradeIntent(id={self.id}, symbol='{self.symbol}', direction='{self.direction}')>"


class TradeEvaluation(Base):
    """Evaluation result for a trade intent.

    Stores the overall evaluation score and summary,
    with individual findings in TradeEvaluationItem.
    """

    __tablename__ = "trade_evaluations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    intent_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("trade_intents.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Multi-scope evaluation support
    campaign_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("position_campaigns.id", ondelete="CASCADE"),
        nullable=True,
    )
    leg_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("campaign_legs.id", ondelete="CASCADE"),
        nullable=True,
    )
    eval_scope: Mapped[str] = mapped_column(String(20), default="intent", nullable=False)
    overall_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Evaluation results
    score: Mapped[float] = mapped_column(Float, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    # Aggregated counts
    blocker_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    info_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Evaluators that were run
    evaluators_run: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Timestamps
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    intent: Mapped[Optional["TradeIntent"]] = relationship("TradeIntent", back_populates="evaluation")
    items: Mapped[list["TradeEvaluationItem"]] = relationship(
        "TradeEvaluationItem",
        back_populates="evaluation",
        cascade="all, delete-orphan",
        order_by="desc(TradeEvaluationItem.severity_priority)",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_eval_score_range"),
        CheckConstraint("blocker_count >= 0", name="ck_eval_blocker_count"),
        CheckConstraint("critical_count >= 0", name="ck_eval_critical_count"),
        CheckConstraint("warning_count >= 0", name="ck_eval_warning_count"),
        CheckConstraint("info_count >= 0", name="ck_eval_info_count"),
        CheckConstraint(
            "eval_scope IN ('intent', 'campaign', 'leg')",
            name="ck_eval_scope",
        ),
        CheckConstraint(
            "overall_label IS NULL OR overall_label IN ('aligned', 'mixed', 'fragile', 'deviates')",
            name="ck_eval_overall_label",
        ),
        Index("ix_trade_evaluations_score", "score"),
        Index("ix_trade_evaluations_campaign", "campaign_id"),
        Index("ix_trade_evaluations_leg", "leg_id"),
    )

    def __repr__(self) -> str:
        return f"<TradeEvaluation(id={self.id}, score={self.score})>"


class TradeEvaluationItem(Base):
    """Individual evaluation finding.

    Stores one check result from an evaluator with
    severity, message, and supporting evidence.
    """

    __tablename__ = "trade_evaluation_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    evaluation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("trade_evaluations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Item identification
    evaluator: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)

    # Severity (info, warning, critical, blocker)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    severity_priority: Mapped[int] = mapped_column(Integer, nullable=False)  # For sorting

    # Content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Dimension grouping for UI cards
    dimension_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Evidence (structured JSONB)
    evidence: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Chart render instructions
    visuals: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    evaluation: Mapped["TradeEvaluation"] = relationship("TradeEvaluation", back_populates="items")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical', 'blocker')",
            name="ck_item_severity"
        ),
        Index("ix_eval_items_evaluator", "evaluator"),
        Index("ix_eval_items_severity", "severity"),
    )

    def __repr__(self) -> str:
        return f"<TradeEvaluationItem(id={self.id}, code='{self.code}', severity='{self.severity}')>"
