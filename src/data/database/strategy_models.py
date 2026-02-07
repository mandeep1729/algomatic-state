"""SQLAlchemy ORM model for user-defined trading strategies.

Defines:
- Strategy: Normalized, user-scoped strategy entity with unique name per account.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.database.models import Base


class Strategy(Base):
    """User-defined trading strategy.

    Provides a normalized, first-class entity for strategy tagging.
    Strategy names are unique per account. Trades reference strategies
    via FK rather than free-text, ensuring consistency.
    """

    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    account: Mapped["UserAccount"] = relationship("UserAccount")

    __table_args__ = (
        UniqueConstraint("account_id", "name", name="uq_strategy_account_name"),
        Index("ix_strategies_account_id", "account_id"),
    )

    def __repr__(self) -> str:
        return f"<Strategy(id={self.id}, name='{self.name}', account_id={self.account_id})>"
