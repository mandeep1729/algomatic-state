"""Thread-safe in-memory message bus for publish/subscribe communication."""

import asyncio
import logging
import threading
from typing import Callable

from src.messaging.base import MessageBusBase, Subscriber
from src.messaging.events import Event, EventType

logger = logging.getLogger(__name__)


class InMemoryMessageBus(MessageBusBase):
    """Thread-safe in-memory publish/subscribe message bus.

    Publish is synchronous: when ``publish()`` returns, all subscribers
    have been called.  This is intentional — the trading-buddy evaluate
    flow requires data to be in the DB *before* the context builder reads it.

    Subscriber errors are isolated; one failing callback does not prevent
    the remaining subscribers from being notified.
    """

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[Subscriber]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: EventType, callback: Subscriber) -> None:
        """Register *callback* to be called when *event_type* is published.

        Args:
            event_type: The event type to listen for.
            callback: A callable that accepts an ``Event``.
        """
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(callback)
        logger.info("Subscribed %s to %s", callback, event_type.value)

    def unsubscribe(self, event_type: EventType, callback: Subscriber) -> None:
        """Remove a previously registered subscriber.

        Silently ignores callbacks that are not subscribed.

        Args:
            event_type: The event type the callback was listening to.
            callback: The callback to remove.
        """
        with self._lock:
            callbacks = self._subscribers.get(event_type, [])
            try:
                callbacks.remove(callback)
                logger.debug("Unsubscribed %s from %s", callback, event_type.value)
            except ValueError:
                pass

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers of its type.

        Subscribers are called inline (synchronously).  If a subscriber
        is a coroutine function, it is scheduled on the running event loop
        (if one exists) via ``asyncio.get_running_loop().create_task()``.

        Errors in individual subscribers are logged and swallowed so that
        one broken subscriber cannot block the rest.

        Args:
            event: The event to publish.
        """
        with self._lock:
            callbacks = list(self._subscribers.get(event.event_type, []))

        if not callbacks:
            logger.debug(
                "No subscribers for %s (correlation_id=%s)",
                event.event_type.value,
                event.correlation_id,
            )
            return

        logger.info(
            "Publishing %s to %d subscriber(s) (correlation_id=%s, source=%s)",
            event.event_type.value,
            len(callbacks),
            event.correlation_id,
            event.source,
        )

        for callback in callbacks:
            try:
                result = callback(event)
                # If the callback returned a coroutine, schedule it
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        # No running loop — run synchronously
                        asyncio.run(result)
            except Exception:
                logger.exception(
                    "Subscriber %s failed for %s (correlation_id=%s)",
                    callback,
                    event.event_type.value,
                    event.correlation_id,
                )


# Backward-compatible alias
MessageBus = InMemoryMessageBus


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_message_bus: MessageBusBase | None = None
_singleton_lock = threading.Lock()


def get_message_bus() -> MessageBusBase:
    """Return the process-wide ``MessageBus`` singleton.

    The backend is determined by ``settings.messaging.backend``:
    - ``"memory"`` (default): :class:`InMemoryMessageBus`
    - ``"redis"``: :class:`~src.messaging.redis_bus.RedisMessageBus`
    """
    global _message_bus
    if _message_bus is None:
        with _singleton_lock:
            if _message_bus is None:
                _message_bus = _create_bus()
                logger.info("Created MessageBus singleton (%s)", type(_message_bus).__name__)
    return _message_bus


def _create_bus() -> MessageBusBase:
    """Instantiate the configured message bus backend."""
    try:
        from config.settings import get_settings
        backend = get_settings().messaging.backend
    except Exception:
        backend = "memory"

    if backend == "redis":
        try:
            from src.messaging.redis_bus import RedisMessageBus
            return RedisMessageBus()
        except Exception:
            logger.warning("Failed to create RedisMessageBus, falling back to InMemoryMessageBus", exc_info=True)
            return InMemoryMessageBus()

    return InMemoryMessageBus()


def reset_message_bus() -> None:
    """Replace the singleton with a fresh instance.

    Intended for test isolation.
    """
    global _message_bus
    with _singleton_lock:
        if _message_bus is not None:
            _message_bus.shutdown()
        _message_bus = None
    logger.debug("MessageBus singleton reset")
