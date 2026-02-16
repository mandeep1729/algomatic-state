"""Abstract base class for message bus implementations."""

import logging
from abc import ABC, abstractmethod
from typing import Callable

from src.messaging.events import Event, EventType

logger = logging.getLogger(__name__)

# Type alias for subscriber callbacks
Subscriber = Callable[[Event], None]


class MessageBusBase(ABC):
    """Abstract interface for publish/subscribe message bus implementations.

    Concrete implementations must provide subscribe, unsubscribe, and publish.
    ``publish_and_wait`` has a default implementation using ``threading.Event``
    but can be overridden for cross-process semantics.
    """

    @abstractmethod
    def subscribe(self, event_type: EventType, callback: Subscriber) -> None:
        """Register *callback* to be called when *event_type* is published.

        Args:
            event_type: The event type to listen for.
            callback: A callable that accepts an ``Event``.
        """

    @abstractmethod
    def unsubscribe(self, event_type: EventType, callback: Subscriber) -> None:
        """Remove a previously registered subscriber.

        Silently ignores callbacks that are not subscribed.

        Args:
            event_type: The event type the callback was listening to.
            callback: The callback to remove.
        """

    @abstractmethod
    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers of its type.

        Args:
            event: The event to publish.
        """

    def publish_and_wait(
        self,
        request: Event,
        response_type: EventType,
        *,
        timeout: float = 30.0,
    ) -> Event | None:
        """Publish *request* and block until a matching response arrives.

        Matching is done via ``correlation_id``.  Returns ``None`` on timeout.

        Args:
            request: The event to publish.
            response_type: The event type to wait for.
            timeout: Maximum seconds to wait.

        Returns:
            The response ``Event``, or ``None`` if timed out.
        """
        import threading

        logger.debug(
            "publish_and_wait: request_type=%s, response_type=%s, correlation_id=%s, timeout=%.1f",
            request.event_type, response_type, request.correlation_id, timeout,
        )

        result: list[Event] = []
        done = threading.Event()

        def _waiter(event: Event) -> None:
            if event.correlation_id == request.correlation_id:
                result.append(event)
                done.set()

        self.subscribe(response_type, _waiter)
        try:
            self.publish(request)
            done.wait(timeout=timeout)
        finally:
            self.unsubscribe(response_type, _waiter)

        if result:
            logger.debug(
                "publish_and_wait: received response for correlation_id=%s",
                request.correlation_id,
            )
        else:
            logger.warning(
                "publish_and_wait: timed out after %.1fs waiting for %s (correlation_id=%s)",
                timeout, response_type, request.correlation_id,
            )

        return result[0] if result else None

    def shutdown(self) -> None:
        """Release resources held by the bus. Override in subclasses."""
        logger.info("Message bus shutting down")

    def health_check(self) -> bool:
        """Return ``True`` if the bus is operational. Override in subclasses."""
        logger.debug("Message bus health check: OK")
        return True
