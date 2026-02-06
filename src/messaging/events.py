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
