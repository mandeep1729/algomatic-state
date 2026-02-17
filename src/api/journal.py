"""FastAPI router for trading journal endpoints.

Provides:
- GET  /api/journal/entries — list journal entries
- POST /api/journal/entries — create a new journal entry
- PUT  /api/journal/entries/{id} — update a journal entry
- GET  /api/journal/tags — list behavioral tags
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.auth_middleware import get_current_user
from src.data.database.dependencies import get_db
from src.data.database.journal_models import JournalEntry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/journal", tags=["journal"])


# -----------------------------------------------------------------------------
# Response / Request Models
# -----------------------------------------------------------------------------

class JournalEntryResponse(BaseModel):
    """Journal entry response matching frontend JournalEntry interface."""
    id: str
    date: str
    type: str
    content: str
    trade_id: Optional[str] = None
    tags: list[str]
    mood: Optional[str] = None
    created_at: str
    updated_at: str


class JournalEntryCreate(BaseModel):
    """Create a new journal entry."""
    date: str
    type: str  # daily_reflection, trade_note
    content: str
    trade_id: Optional[str] = None
    tags: list[str] = []
    mood: Optional[str] = None


class JournalEntryUpdate(BaseModel):
    """Update an existing journal entry."""
    date: Optional[str] = None
    type: Optional[str] = None
    content: Optional[str] = None
    trade_id: Optional[str] = None
    tags: Optional[list[str]] = None
    mood: Optional[str] = None


class BehavioralTagResponse(BaseModel):
    """Behavioral tag definition."""
    name: str
    category: str
    description: str


# Predefined behavioral tags (same as mock data)
BEHAVIORAL_TAGS = [
    {"name": "fomo", "category": "emotional", "description": "Fear of missing out drove the entry"},
    {"name": "revenge_trade", "category": "emotional", "description": "Entering to recover previous losses"},
    {"name": "overconfident", "category": "emotional", "description": "Excessive confidence after recent wins"},
    {"name": "hesitated", "category": "emotional", "description": "Delayed entry due to fear or doubt"},
    {"name": "followed_plan", "category": "process", "description": "Trade aligned with defined strategy"},
    {"name": "deviated", "category": "process", "description": "Broke from planned strategy rules"},
    {"name": "no_stop_loss", "category": "risk", "description": "Entered without a stop loss"},
    {"name": "oversized", "category": "risk", "description": "Position size exceeded risk limits"},
    {"name": "moved_stop", "category": "risk", "description": "Moved stop loss after entry"},
    {"name": "early_entry", "category": "timing", "description": "Entered before confirmation signal"},
    {"name": "late_entry", "category": "timing", "description": "Entered after the move already started"},
    {"name": "chased", "category": "timing", "description": "Entered at an extended price level"},
]


# -----------------------------------------------------------------------------
# Helper
# -----------------------------------------------------------------------------

def _format_dt(dt) -> str:
    """Format a datetime to ISO 8601 string with Z suffix."""
    if dt is None:
        return ""
    s = dt.isoformat()
    if "+00:00" in s:
        s = s.replace("+00:00", "Z")
    elif not s.endswith("Z"):
        s += "Z"
    return s


def _entry_to_response(entry: JournalEntry) -> JournalEntryResponse:
    """Convert a JournalEntry ORM model to a response."""
    return JournalEntryResponse(
        id=str(entry.id),
        date=entry.date,
        type=entry.entry_type,
        content=entry.content,
        trade_id=entry.trade_id,
        tags=entry.tags or [],
        mood=entry.mood,
        created_at=_format_dt(entry.created_at),
        updated_at=_format_dt(entry.updated_at),
    )


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get("/entries", response_model=list[JournalEntryResponse])
async def list_journal_entries(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List journal entries for the authenticated user, newest first."""
    entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.account_id == user_id)
        .order_by(JournalEntry.date.desc(), JournalEntry.created_at.desc())
        .limit(200)
        .all()
    )
    logger.debug("Listed %d journal entries for user_id=%d", len(entries), user_id)
    return [_entry_to_response(e) for e in entries]


@router.post("/entries", response_model=JournalEntryResponse, status_code=201)
async def create_journal_entry(
    data: JournalEntryCreate,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new journal entry."""
    if not data.content.strip():
        raise HTTPException(status_code=400, detail="Content is required")

    entry = JournalEntry(
        account_id=user_id,
        date=data.date,
        entry_type=data.type,
        content=data.content,
        trade_id=data.trade_id,
        tags=data.tags,
        mood=data.mood,
    )
    db.add(entry)
    db.flush()

    logger.info("Created journal entry id=%s date=%s for user_id=%d", entry.id, data.date, user_id)
    return _entry_to_response(entry)


@router.put("/entries/{entry_id}", response_model=JournalEntryResponse)
async def update_journal_entry(
    entry_id: int,
    data: JournalEntryUpdate,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an existing journal entry."""
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail=f"Journal entry {entry_id} not found")

    if entry.account_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this entry")

    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Map 'type' to 'entry_type' for the DB column
    if "type" in updates:
        updates["entry_type"] = updates.pop("type")

    for key, value in updates.items():
        if hasattr(entry, key):
            setattr(entry, key, value)

    db.flush()

    logger.info("Updated journal entry id=%s fields=%s for user_id=%d", entry_id, list(updates.keys()), user_id)
    return _entry_to_response(entry)


@router.get("/tags", response_model=list[BehavioralTagResponse])
async def list_behavioral_tags(user_id: int = Depends(get_current_user)):
    """List predefined behavioral tags."""
    return [BehavioralTagResponse(**tag) for tag in BEHAVIORAL_TAGS]
