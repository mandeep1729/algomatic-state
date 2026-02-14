"""Event types and data structures for the messaging system."""

import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events that can flow through the message bus."""

    MARKET_DATA_REQUEST = "market_data_request"
    MARKET_DATA_UPDATED = "market_data_updated"
    MARKET_DATA_FAILED = "market_data_failed"

    INDICATOR_COMPUTE_REQUEST = "indicator_compute_request"
    INDICATOR_COMPUTE_COMPLETE = "indicator_compute_complete"
    INDICATOR_COMPUTE_FAILED = "indicator_compute_failed"

    REVIEW_LEG_CREATED = "review_leg_created"
    REVIEW_CONTEXT_UPDATED = "review_context_updated"
    REVIEW_RISK_PREFS_UPDATED = "review_risk_prefs_updated"
    REVIEW_CAMPAIGNS_POPULATED = "review_campaigns_populated"
    REVIEW_COMPLETE = "review_complete"
    REVIEW_FAILED = "review_failed"


@dataclass(frozen=True)
class Event:
    """Immutable event flowing through the message bus.

    Attributes:
        event_type: The kind of event.
        payload: Arbitrary data carried by the event.
        source: Identifier of the component that published the event.
        timestamp: When the event was created (UTC).
        correlation_id: Ties related request/response events together.
    """

    event_type: EventType
    payload: dict
    source: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        from src.messaging.serialization import event_to_dict
        return event_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        """Deserialize from a dictionary."""
        from src.messaging.serialization import event_from_dict
        return event_from_dict(data)
