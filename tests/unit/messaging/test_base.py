"""Tests for the MessageBusBase ABC contract."""

import threading

import pytest

from src.messaging.base import MessageBusBase, Subscriber
from src.messaging.bus import InMemoryMessageBus
from src.messaging.events import Event, EventType


def _make_event(event_type=EventType.MARKET_DATA_REQUEST, **overrides):
    defaults = dict(event_type=event_type, payload={"symbol": "AAPL"}, source="test")
    defaults.update(overrides)
    return Event(**defaults)


class TestMessageBusBaseContract:
    """Verify InMemoryMessageBus satisfies the ABC contract."""

    def test_is_subclass(self):
        assert issubclass(InMemoryMessageBus, MessageBusBase)

    def test_instance_check(self):
        bus = InMemoryMessageBus()
        assert isinstance(bus, MessageBusBase)

    def test_cannot_instantiate_abc_directly(self):
        with pytest.raises(TypeError):
            MessageBusBase()


class TestPublishAndWait:
    """Tests for the default publish_and_wait on MessageBusBase."""

    def test_returns_matching_response(self):
        bus = InMemoryMessageBus()
        request = _make_event(EventType.MARKET_DATA_REQUEST)

        # Simulate a responder that replies on MARKET_DATA_UPDATED
        def responder(event: Event) -> None:
            bus.publish(Event(
                event_type=EventType.MARKET_DATA_UPDATED,
                payload={"result": "ok"},
                source="responder",
                correlation_id=event.correlation_id,
            ))

        bus.subscribe(EventType.MARKET_DATA_REQUEST, responder)

        response = bus.publish_and_wait(
            request,
            EventType.MARKET_DATA_UPDATED,
            timeout=5.0,
        )

        assert response is not None
        assert response.correlation_id == request.correlation_id
        assert response.payload == {"result": "ok"}

    def test_returns_none_on_timeout(self):
        bus = InMemoryMessageBus()
        request = _make_event(EventType.MARKET_DATA_REQUEST)

        # No responder registered — should time out
        response = bus.publish_and_wait(
            request,
            EventType.MARKET_DATA_UPDATED,
            timeout=0.1,
        )

        assert response is None

    def test_ignores_non_matching_correlation_id(self):
        bus = InMemoryMessageBus()
        request = _make_event(EventType.MARKET_DATA_REQUEST)

        # Responder replies with a different correlation_id
        def bad_responder(event: Event) -> None:
            bus.publish(Event(
                event_type=EventType.MARKET_DATA_UPDATED,
                payload={"result": "wrong"},
                source="responder",
                correlation_id="different-id",
            ))

        bus.subscribe(EventType.MARKET_DATA_REQUEST, bad_responder)

        response = bus.publish_and_wait(
            request,
            EventType.MARKET_DATA_UPDATED,
            timeout=0.1,
        )

        assert response is None


class TestHealthCheckAndShutdown:
    """Default implementations should be safe to call."""

    def test_health_check_default_returns_true(self):
        bus = InMemoryMessageBus()
        assert bus.health_check() is True

    def test_shutdown_is_noop(self):
        bus = InMemoryMessageBus()
        bus.shutdown()  # Should not raise
