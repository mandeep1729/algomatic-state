"""SQLAlchemy ORM models for Trading Buddy platform.

Defines tables for:
- UserAccount: User account with auth and personal details
- UserProfile: Trading/risk preferences (1-to-1 with UserAccount)
- UserRule: Custom evaluation rules per user
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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

    def __repr__(self) -> str:
        return f"<UserAccount(id={self.id}, name='{self.name}')>"


class UserProfile(Base):
    """Trading and risk preferences for a user.

    One-to-one relationship with UserAccount. Uses two JSONB columns:
    - profile: account_balance, default_timeframes, experience_level, trading_style
    - risk_profile: max_position_size_pct, max_risk_per_trade_pct,
                    max_daily_loss_pct, min_risk_reward_ratio
    """

    __tablename__ = "user_profiles"

    # Default values for profile fields
    PROFILE_DEFAULTS: dict = {
        "account_balance": 0.0,
        "default_timeframes": ["1Min", "5Min", "15Min", "1Hour"],
        "experience_level": None,
        "trading_style": None,
        "primary_markets": ["US_EQUITIES"],
        "account_size_range": None,
        "evaluation_controls": None,
    }

    # Default values for risk_profile fields
    RISK_PROFILE_DEFAULTS: dict = {
        "max_position_size_pct": 5.0,
        "max_risk_per_trade_pct": 1.0,
        "max_daily_loss_pct": 3.0,
        "min_risk_reward_ratio": 2.0,
        "max_open_positions": 5,
        "stop_loss_required": True,
    }

    # Default values for site_prefs fields
    SITE_PREF_DEFAULTS: dict = {
        "theme": "light",
        "sidebar_collapsed": False,
        "notifications_enabled": True,
        "language": "en",
    }

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # JSONB columns for flexible profile and risk data
    profile: Mapped[dict] = mapped_column(
        JSONB, default=lambda: dict(UserProfile.PROFILE_DEFAULTS), nullable=False
    )
    risk_profile: Mapped[dict] = mapped_column(
        JSONB, default=lambda: dict(UserProfile.RISK_PROFILE_DEFAULTS), nullable=False
    )

    # Site/UI preferences (optional JSONB)
    site_prefs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Aggregated trading statistics (optional JSONB)
    stats: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

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

    # ---- Convenience properties for profile fields ----

    @property
    def account_balance(self) -> float:
        """Account balance from profile JSONB."""
        return (self.profile or {}).get("account_balance", self.PROFILE_DEFAULTS["account_balance"])

    @account_balance.setter
    def account_balance(self, value: float) -> None:
        if self.profile is None:
            self.profile = dict(self.PROFILE_DEFAULTS)
        self.profile = {**self.profile, "account_balance": value}

    @property
    def default_timeframes(self) -> list[str]:
        """Default timeframes from profile JSONB."""
        return (self.profile or {}).get(
            "default_timeframes", self.PROFILE_DEFAULTS["default_timeframes"]
        )

    @default_timeframes.setter
    def default_timeframes(self, value: list[str]) -> None:
        if self.profile is None:
            self.profile = dict(self.PROFILE_DEFAULTS)
        self.profile = {**self.profile, "default_timeframes": value}

    @property
    def experience_level(self) -> Optional[str]:
        """Experience level from profile JSONB."""
        return (self.profile or {}).get("experience_level")

    @experience_level.setter
    def experience_level(self, value: Optional[str]) -> None:
        if self.profile is None:
            self.profile = dict(self.PROFILE_DEFAULTS)
        self.profile = {**self.profile, "experience_level": value}

    @property
    def trading_style(self) -> Optional[str]:
        """Trading style from profile JSONB."""
        return (self.profile or {}).get("trading_style")

    @trading_style.setter
    def trading_style(self, value: Optional[str]) -> None:
        if self.profile is None:
            self.profile = dict(self.PROFILE_DEFAULTS)
        self.profile = {**self.profile, "trading_style": value}

    # ---- Convenience properties for risk_profile fields ----

    @property
    def max_position_size_pct(self) -> float:
        """Max position size % from risk_profile JSONB."""
        return (self.risk_profile or {}).get(
            "max_position_size_pct", self.RISK_PROFILE_DEFAULTS["max_position_size_pct"]
        )

    @max_position_size_pct.setter
    def max_position_size_pct(self, value: float) -> None:
        if self.risk_profile is None:
            self.risk_profile = dict(self.RISK_PROFILE_DEFAULTS)
        self.risk_profile = {**self.risk_profile, "max_position_size_pct": value}

    @property
    def max_risk_per_trade_pct(self) -> float:
        """Max risk per trade % from risk_profile JSONB."""
        return (self.risk_profile or {}).get(
            "max_risk_per_trade_pct", self.RISK_PROFILE_DEFAULTS["max_risk_per_trade_pct"]
        )

    @max_risk_per_trade_pct.setter
    def max_risk_per_trade_pct(self, value: float) -> None:
        if self.risk_profile is None:
            self.risk_profile = dict(self.RISK_PROFILE_DEFAULTS)
        self.risk_profile = {**self.risk_profile, "max_risk_per_trade_pct": value}

    @property
    def max_daily_loss_pct(self) -> float:
        """Max daily loss % from risk_profile JSONB."""
        return (self.risk_profile or {}).get(
            "max_daily_loss_pct", self.RISK_PROFILE_DEFAULTS["max_daily_loss_pct"]
        )

    @max_daily_loss_pct.setter
    def max_daily_loss_pct(self, value: float) -> None:
        if self.risk_profile is None:
            self.risk_profile = dict(self.RISK_PROFILE_DEFAULTS)
        self.risk_profile = {**self.risk_profile, "max_daily_loss_pct": value}

    @property
    def min_risk_reward_ratio(self) -> float:
        """Min risk/reward ratio from risk_profile JSONB."""
        return (self.risk_profile or {}).get(
            "min_risk_reward_ratio", self.RISK_PROFILE_DEFAULTS["min_risk_reward_ratio"]
        )

    @min_risk_reward_ratio.setter
    def min_risk_reward_ratio(self, value: float) -> None:
        if self.risk_profile is None:
            self.risk_profile = dict(self.RISK_PROFILE_DEFAULTS)
        self.risk_profile = {**self.risk_profile, "min_risk_reward_ratio": value}

    @property
    def max_open_positions(self) -> int:
        """Max open positions from risk_profile JSONB."""
        return (self.risk_profile or {}).get(
            "max_open_positions", self.RISK_PROFILE_DEFAULTS["max_open_positions"]
        )

    @max_open_positions.setter
    def max_open_positions(self, value: int) -> None:
        if self.risk_profile is None:
            self.risk_profile = dict(self.RISK_PROFILE_DEFAULTS)
        self.risk_profile = {**self.risk_profile, "max_open_positions": value}

    @property
    def stop_loss_required(self) -> bool:
        """Whether stop loss is required from risk_profile JSONB."""
        return (self.risk_profile or {}).get(
            "stop_loss_required", self.RISK_PROFILE_DEFAULTS["stop_loss_required"]
        )

    @stop_loss_required.setter
    def stop_loss_required(self, value: bool) -> None:
        if self.risk_profile is None:
            self.risk_profile = dict(self.RISK_PROFILE_DEFAULTS)
        self.risk_profile = {**self.risk_profile, "stop_loss_required": value}

    # ---- Convenience properties for new profile fields ----

    @property
    def primary_markets(self) -> Optional[list]:
        """Primary markets from profile JSONB."""
        return (self.profile or {}).get(
            "primary_markets", self.PROFILE_DEFAULTS["primary_markets"]
        )

    @primary_markets.setter
    def primary_markets(self, value: Optional[list]) -> None:
        if self.profile is None:
            self.profile = dict(self.PROFILE_DEFAULTS)
        self.profile = {**self.profile, "primary_markets": value}

    @property
    def account_size_range(self) -> Optional[str]:
        """Account size range from profile JSONB."""
        return (self.profile or {}).get("account_size_range")

    @account_size_range.setter
    def account_size_range(self, value: Optional[str]) -> None:
        if self.profile is None:
            self.profile = dict(self.PROFILE_DEFAULTS)
        self.profile = {**self.profile, "account_size_range": value}

    @property
    def evaluation_controls(self) -> Optional[dict]:
        """Evaluation controls from profile JSONB."""
        return (self.profile or {}).get("evaluation_controls")

    @evaluation_controls.setter
    def evaluation_controls(self, value: Optional[dict]) -> None:
        if self.profile is None:
            self.profile = dict(self.PROFILE_DEFAULTS)
        self.profile = {**self.profile, "evaluation_controls": value}

    # ---- Convenience properties for site_prefs fields ----

    @property
    def theme(self) -> str:
        """UI theme from site_prefs JSONB."""
        return (self.site_prefs or {}).get("theme", self.SITE_PREF_DEFAULTS["theme"])

    @theme.setter
    def theme(self, value: str) -> None:
        if self.site_prefs is None:
            self.site_prefs = dict(self.SITE_PREF_DEFAULTS)
        self.site_prefs = {**self.site_prefs, "theme": value}

    @property
    def sidebar_collapsed(self) -> bool:
        """Sidebar collapsed state from site_prefs JSONB."""
        return (self.site_prefs or {}).get(
            "sidebar_collapsed", self.SITE_PREF_DEFAULTS["sidebar_collapsed"]
        )

    @sidebar_collapsed.setter
    def sidebar_collapsed(self, value: bool) -> None:
        if self.site_prefs is None:
            self.site_prefs = dict(self.SITE_PREF_DEFAULTS)
        self.site_prefs = {**self.site_prefs, "sidebar_collapsed": value}

    @property
    def notifications_enabled(self) -> bool:
        """Notifications enabled state from site_prefs JSONB."""
        return (self.site_prefs or {}).get(
            "notifications_enabled", self.SITE_PREF_DEFAULTS["notifications_enabled"]
        )

    @notifications_enabled.setter
    def notifications_enabled(self, value: bool) -> None:
        if self.site_prefs is None:
            self.site_prefs = dict(self.SITE_PREF_DEFAULTS)
        self.site_prefs = {**self.site_prefs, "notifications_enabled": value}

    @property
    def language(self) -> str:
        """Language preference from site_prefs JSONB."""
        return (self.site_prefs or {}).get("language", self.SITE_PREF_DEFAULTS["language"])

    @language.setter
    def language(self, value: str) -> None:
        if self.site_prefs is None:
            self.site_prefs = dict(self.SITE_PREF_DEFAULTS)
        self.site_prefs = {**self.site_prefs, "language": value}

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


class Waitlist(Base):
    """Waitlist entry for users requesting platform access.

    Status values:
    - waiting: submitted interest, pending manual approval
    - approved: approved for account creation
    - rejected: denied access
    """

    __tablename__ = "waitlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="waiting", nullable=False)
    referral_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
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

    __table_args__ = (
        CheckConstraint(
            "status IN ('waiting', 'approved', 'rejected')",
            name="ck_waitlist_status",
        ),
        Index("ix_waitlist_email", "email"),
        Index("ix_waitlist_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Waitlist(id={self.id}, email='{self.email}', status='{self.status}')>"
