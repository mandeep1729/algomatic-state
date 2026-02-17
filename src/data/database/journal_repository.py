"""Repository for trading journal data access.

Centralizes all journal_entries queries previously in src/api/journal.py.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.data.database.journal_models import JournalEntry

logger = logging.getLogger(__name__)


class JournalRepository:
    """Repository for trading journal entry operations."""

    def __init__(self, session: Session):
        self.session = session

    def list_entries(
        self,
        account_id: int,
        limit: int = 200,
    ) -> list[JournalEntry]:
        """List journal entries for an account, newest first."""
        return (
            self.session.query(JournalEntry)
            .filter(JournalEntry.account_id == account_id)
            .order_by(JournalEntry.date.desc(), JournalEntry.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_entry(self, entry_id: int) -> Optional[JournalEntry]:
        """Get a journal entry by ID."""
        return self.session.query(JournalEntry).filter(
            JournalEntry.id == entry_id,
        ).first()

    def create_entry(self, **kwargs) -> JournalEntry:
        """Create a new journal entry."""
        entry = JournalEntry(**kwargs)
        self.session.add(entry)
        self.session.flush()
        logger.info(
            "Created journal entry id=%s date=%s for account_id=%d",
            entry.id,
            entry.date,
            entry.account_id,
        )
        return entry

    def update_entry(
        self,
        entry_id: int,
        account_id: int,
        **kwargs,
    ) -> Optional[JournalEntry]:
        """Update a journal entry. Returns None if not found or not authorized.

        Args:
            entry_id: Journal entry ID.
            account_id: Account ID for authorization check.
            **kwargs: Fields to update (already mapped to DB column names).

        Returns:
            Updated JournalEntry or None.
        """
        entry = self.get_entry(entry_id)
        if not entry:
            return None
        if entry.account_id != account_id:
            return None

        for key, value in kwargs.items():
            if hasattr(entry, key):
                setattr(entry, key, value)

        self.session.flush()
        logger.info(
            "Updated journal entry id=%s fields=%s",
            entry_id,
            list(kwargs.keys()),
        )
        return entry
