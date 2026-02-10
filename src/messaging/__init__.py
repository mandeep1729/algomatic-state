"""Messaging system for decoupling producers and consumers.

Supports in-memory (default) and Redis-backed pub/sub backends.
"""

from src.messaging.events import Event, EventType
from src.messaging.base import MessageBusBase, Subscriber
from src.messaging.bus import (
    InMemoryMessageBus,
    MessageBus,
    get_message_bus,
    reset_message_bus,
)

__all__ = [
    "Event",
    "EventType",
    "MessageBusBase",
    "Subscriber",
    "InMemoryMessageBus",
    "MessageBus",
    "get_message_bus",
    "reset_message_bus",
]
