"""SQLAlchemy ORM model for trading journal entries.

Defines:
- JournalEntry: User-scoped journal entries for daily reflections and trade notes.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.database.models import Base


class JournalEntry(Base):
    """Trading journal entry.

    Supports daily reflections and trade-specific notes with
    behavioral tagging and mood tracking.
    """

    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Entry content
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)  # daily_reflection, trade_note
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional trade association
    trade_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Behavioral tags (JSONB array of strings)
    tags: Mapped[Optional[dict]] = mapped_column(JSONB, default=list, nullable=True)

    # Mood tracking
    mood: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

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
    account: Mapped["UserAccount"] = relationship("UserAccount")

    __table_args__ = (
        Index("ix_journal_entries_account_id", "account_id"),
        Index("ix_journal_entries_date", "date"),
        Index("ix_journal_entries_account_date", "account_id", "date"),
    )

    def __repr__(self) -> str:
        return f"<JournalEntry(id={self.id}, date='{self.date}', type='{self.entry_type}')>"
