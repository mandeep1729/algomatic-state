"""Tests for the trading journal API endpoints.

Endpoints under test:
- GET  /api/journal/entries
- POST /api/journal/entries
- PUT  /api/journal/entries/{id}
- GET  /api/journal/tags
"""

import pytest
from sqlalchemy.orm import Session

from tests.unit.api.conftest import TEST_USER_ID, OTHER_USER_ID


def _create_journal_entry(db_session: Session, account_id: int, **kwargs):
    """Helper to insert a journal entry directly into the database."""
    from src.data.database.journal_models import JournalEntry

    entry = JournalEntry(
        account_id=account_id,
        date=kwargs.get("date", "2025-01-15"),
        entry_type=kwargs.get("entry_type", "daily_reflection"),
        content=kwargs.get("content", "Market was choppy today."),
        trade_id=kwargs.get("trade_id"),
        tags=kwargs.get("tags", ["followed_plan"]),
        mood=kwargs.get("mood", "neutral"),
    )
    db_session.add(entry)
    db_session.flush()
    return entry


# ---------------------------------------------------------------------------
# List Journal Entries
# ---------------------------------------------------------------------------


class TestListJournalEntries:
    """GET /api/journal/entries"""

    def test_empty_list_for_new_user(self, client, test_account):
        """User with no entries should get an empty list."""
        response = client.get("/api/journal/entries")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_user_entries(self, client, test_account, db_session: Session):
        """Should return all entries for the authenticated user."""
        _create_journal_entry(db_session, TEST_USER_ID, date="2025-01-10")
        _create_journal_entry(db_session, TEST_USER_ID, date="2025-01-11")

        response = client.get("/api/journal/entries")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2

    def test_does_not_return_other_users_entries(
        self, client, test_account, other_account, db_session: Session
    ):
        """Multi-tenant isolation: should not see other user's entries."""
        _create_journal_entry(db_session, TEST_USER_ID, date="2025-01-10")
        _create_journal_entry(db_session, OTHER_USER_ID, date="2025-01-10")

        response = client.get("/api/journal/entries")
        data = response.json()
        assert len(data) == 1

    def test_entries_ordered_by_date_desc(self, client, test_account, db_session: Session):
        """Entries should be returned with newest first."""
        _create_journal_entry(db_session, TEST_USER_ID, date="2025-01-01")
        _create_journal_entry(db_session, TEST_USER_ID, date="2025-01-15")

        response = client.get("/api/journal/entries")
        data = response.json()
        assert data[0]["date"] == "2025-01-15"
        assert data[1]["date"] == "2025-01-01"


# ---------------------------------------------------------------------------
# Create Journal Entry
# ---------------------------------------------------------------------------


class TestCreateJournalEntry:
    """POST /api/journal/entries"""

    def test_create_with_valid_data(self, client, test_account, db_session: Session):
        """Creating a journal entry with valid data should return 201."""
        payload = {
            "date": "2025-02-01",
            "type": "trade_note",
            "content": "Took profit at resistance.",
            "tags": ["followed_plan", "early_entry"],
            "mood": "confident",
        }
        response = client.post("/api/journal/entries", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["date"] == "2025-02-01"
        assert data["type"] == "trade_note"
        assert data["content"] == "Took profit at resistance."
        assert "followed_plan" in data["tags"]
        assert data["mood"] == "confident"
        assert "id" in data
        assert data["created_at"] != ""
        assert data["updated_at"] != ""

        # Verify in DB
        from src.data.database.journal_models import JournalEntry

        entry = db_session.query(JournalEntry).filter(
            JournalEntry.account_id == TEST_USER_ID
        ).first()
        assert entry is not None
        assert entry.content == "Took profit at resistance."
        assert entry.entry_type == "trade_note"

    def test_create_with_trade_id(self, client, test_account):
        """Should accept optional trade_id field."""
        payload = {
            "date": "2025-02-01",
            "type": "trade_note",
            "content": "Nice setup",
            "trade_id": "campaign_42",
        }
        response = client.post("/api/journal/entries", json=payload)
        assert response.status_code == 201
        assert response.json()["trade_id"] == "campaign_42"

    def test_create_empty_content_returns_400(self, client, test_account):
        """Content must not be empty."""
        payload = {
            "date": "2025-02-01",
            "type": "daily_reflection",
            "content": "   ",
        }
        response = client.post("/api/journal/entries", json=payload)
        assert response.status_code == 400

    def test_create_with_empty_tags_defaults_to_list(self, client, test_account):
        """Tags should default to an empty list when omitted."""
        payload = {
            "date": "2025-02-01",
            "type": "daily_reflection",
            "content": "Good day overall.",
        }
        response = client.post("/api/journal/entries", json=payload)
        assert response.status_code == 201
        assert response.json()["tags"] == []


# ---------------------------------------------------------------------------
# Update Journal Entry
# ---------------------------------------------------------------------------


class TestUpdateJournalEntry:
    """PUT /api/journal/entries/{id}"""

    def test_update_content_and_tags(self, client, test_account, db_session: Session):
        """Should update specified fields on an existing entry."""
        entry = _create_journal_entry(db_session, TEST_USER_ID, content="Original content")

        payload = {"content": "Updated content", "tags": ["fomo"]}
        response = client.put(f"/api/journal/entries/{entry.id}", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["content"] == "Updated content"
        assert data["tags"] == ["fomo"]

        # Verify persistence
        db_session.refresh(entry)
        assert entry.content == "Updated content"
        assert entry.tags == ["fomo"]

    def test_update_nonexistent_returns_404(self, client, test_account):
        """Updating a non-existent entry should return 404."""
        response = client.put("/api/journal/entries/99999", json={"content": "X"})
        assert response.status_code == 404

    def test_update_other_users_entry_returns_403(
        self, client, test_account, other_account, db_session: Session
    ):
        """User should not be able to update another user's entry."""
        other_entry = _create_journal_entry(db_session, OTHER_USER_ID)

        response = client.put(
            f"/api/journal/entries/{other_entry.id}",
            json={"content": "Hacked"},
        )
        assert response.status_code == 403

    def test_update_empty_body_returns_400(self, client, test_account, db_session: Session):
        """Empty update should be rejected."""
        entry = _create_journal_entry(db_session, TEST_USER_ID)
        response = client.put(f"/api/journal/entries/{entry.id}", json={})
        assert response.status_code == 400

    def test_update_preserves_immutable_timestamps(
        self, client, test_account, db_session: Session
    ):
        """created_at should not change on update; updated_at should change."""
        entry = _create_journal_entry(db_session, TEST_USER_ID)
        original_created = entry.created_at

        response = client.put(
            f"/api/journal/entries/{entry.id}",
            json={"mood": "anxious"},
        )
        assert response.status_code == 200

        db_session.refresh(entry)
        assert entry.created_at == original_created


# ---------------------------------------------------------------------------
# Behavioral Tags
# ---------------------------------------------------------------------------


class TestBehavioralTags:
    """GET /api/journal/tags"""

    def test_returns_predefined_tags(self, client, test_account):
        """Should return the list of predefined behavioral tags."""
        response = client.get("/api/journal/tags")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # Verify structure of each tag
        for tag in data:
            assert "name" in tag
            assert "category" in tag
            assert "description" in tag

    def test_known_tag_names_present(self, client, test_account):
        """Core tags like fomo, revenge_trade should be present."""
        response = client.get("/api/journal/tags")
        data = response.json()
        tag_names = {t["name"] for t in data}
        assert "fomo" in tag_names
        assert "revenge_trade" in tag_names
        assert "followed_plan" in tag_names
        assert "no_stop_loss" in tag_names
