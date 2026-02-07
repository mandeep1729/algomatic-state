"""Tests for MessageBus, get_message_bus, and reset_message_bus."""

import threading

import pytest

from src.messaging.bus import MessageBus, get_message_bus, reset_message_bus
from src.messaging.events import Event, EventType


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure a clean singleton for every test."""
    reset_message_bus()
    yield
    reset_message_bus()


def _make_event(event_type=EventType.MARKET_DATA_REQUEST, **overrides):
    """Helper to build an Event with sensible defaults."""
    defaults = dict(
        event_type=event_type,
        payload={"symbol": "AAPL"},
        source="test",
    )
    defaults.update(overrides)
    return Event(**defaults)


# -----------------------------------------------------------------------
# MessageBus core behaviour
# -----------------------------------------------------------------------


class TestSubscribePublish:
    """Basic subscribe and publish flow."""

    def test_subscriber_receives_event(self):
        bus = MessageBus()
        received = []
        bus.subscribe(EventType.MARKET_DATA_REQUEST, received.append)

        event = _make_event()
        bus.publish(event)

        assert len(received) == 1
        assert received[0] is event

    def test_multiple_subscribers_all_called(self):
        bus = MessageBus()
        a, b = [], []
        bus.subscribe(EventType.MARKET_DATA_REQUEST, a.append)
        bus.subscribe(EventType.MARKET_DATA_REQUEST, b.append)

        bus.publish(_make_event())

        assert len(a) == 1
        assert len(b) == 1

    def test_subscriber_not_called_for_other_event_type(self):
        bus = MessageBus()
        received = []
        bus.subscribe(EventType.MARKET_DATA_UPDATED, received.append)

        bus.publish(_make_event(EventType.MARKET_DATA_REQUEST))

        assert received == []

    def test_publish_with_no_subscribers(self):
        """Publishing to an event type with zero subscribers should not raise."""
        bus = MessageBus()
        bus.publish(_make_event())  # no subscribers — should be silent

    def test_same_callback_subscribed_twice(self):
        bus = MessageBus()
        received = []
        bus.subscribe(EventType.MARKET_DATA_REQUEST, received.append)
        bus.subscribe(EventType.MARKET_DATA_REQUEST, received.append)

        bus.publish(_make_event())

        assert len(received) == 2


class TestUnsubscribe:
    """Unsubscribe behaviour."""

    def test_unsubscribe_removes_callback(self):
        bus = MessageBus()
        received = []
        bus.subscribe(EventType.MARKET_DATA_REQUEST, received.append)
        bus.unsubscribe(EventType.MARKET_DATA_REQUEST, received.append)

        bus.publish(_make_event())

        assert received == []

    def test_unsubscribe_unknown_callback_is_silent(self):
        bus = MessageBus()
        bus.unsubscribe(EventType.MARKET_DATA_REQUEST, lambda e: None)
        # Should not raise

    def test_unsubscribe_unknown_event_type_is_silent(self):
        bus = MessageBus()
        bus.unsubscribe(EventType.MARKET_DATA_FAILED, lambda e: None)

    def test_unsubscribe_only_removes_first_occurrence(self):
        bus = MessageBus()
        received = []
        cb = received.append
        bus.subscribe(EventType.MARKET_DATA_REQUEST, cb)
        bus.subscribe(EventType.MARKET_DATA_REQUEST, cb)
        bus.unsubscribe(EventType.MARKET_DATA_REQUEST, cb)

        bus.publish(_make_event())

        # One copy was removed, the other remains
        assert len(received) == 1


class TestErrorIsolation:
    """A failing subscriber must not break other subscribers."""

    def test_error_in_first_subscriber_does_not_block_second(self):
        bus = MessageBus()
        received = []

        def bad(event):
            raise RuntimeError("boom")

        bus.subscribe(EventType.MARKET_DATA_REQUEST, bad)
        bus.subscribe(EventType.MARKET_DATA_REQUEST, received.append)

        bus.publish(_make_event())

        assert len(received) == 1

    def test_error_in_second_subscriber_does_not_affect_first(self):
        bus = MessageBus()
        received = []

        def bad(event):
            raise RuntimeError("boom")

        bus.subscribe(EventType.MARKET_DATA_REQUEST, received.append)
        bus.subscribe(EventType.MARKET_DATA_REQUEST, bad)

        bus.publish(_make_event())

        assert len(received) == 1

    def test_all_errors_still_publishes_to_good_subscriber(self):
        bus = MessageBus()
        received = []

        def bad1(e):
            raise ValueError("one")

        def bad2(e):
            raise TypeError("two")

        bus.subscribe(EventType.MARKET_DATA_REQUEST, bad1)
        bus.subscribe(EventType.MARKET_DATA_REQUEST, received.append)
        bus.subscribe(EventType.MARKET_DATA_REQUEST, bad2)

        bus.publish(_make_event())

        assert len(received) == 1


class TestThreadSafety:
    """Concurrent subscribe/publish must not corrupt state."""

    def test_concurrent_publish(self):
        bus = MessageBus()
        received = []
        lock = threading.Lock()

        def safe_append(event):
            with lock:
                received.append(event)

        bus.subscribe(EventType.MARKET_DATA_REQUEST, safe_append)

        threads = [
            threading.Thread(target=bus.publish, args=(_make_event(),))
            for _ in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(received) == 20

    def test_concurrent_subscribe_and_publish(self):
        bus = MessageBus()
        received = []
        lock = threading.Lock()

        def safe_append(event):
            with lock:
                received.append(event)

        def subscribe_and_publish():
            bus.subscribe(EventType.MARKET_DATA_UPDATED, safe_append)
            bus.publish(_make_event(EventType.MARKET_DATA_UPDATED))

        threads = [
            threading.Thread(target=subscribe_and_publish)
            for _ in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each thread subscribes once then publishes once. The i-th thread
        # sees i subscribers already registered, so total events received
        # is >= 10 (at least one per thread's own publish).
        assert len(received) >= 10


class TestMultipleEventTypes:
    """Subscribers can be registered on different event types independently."""

    def test_separate_event_types(self):
        bus = MessageBus()
        requests, updates, failures = [], [], []

        bus.subscribe(EventType.MARKET_DATA_REQUEST, requests.append)
        bus.subscribe(EventType.MARKET_DATA_UPDATED, updates.append)
        bus.subscribe(EventType.MARKET_DATA_FAILED, failures.append)

        bus.publish(_make_event(EventType.MARKET_DATA_REQUEST))
        bus.publish(_make_event(EventType.MARKET_DATA_UPDATED))

        assert len(requests) == 1
        assert len(updates) == 1
        assert len(failures) == 0


# -----------------------------------------------------------------------
# Singleton management
# -----------------------------------------------------------------------


class TestSingleton:
    """Tests for get_message_bus / reset_message_bus."""

    def test_returns_same_instance(self):
        bus1 = get_message_bus()
        bus2 = get_message_bus()
        assert bus1 is bus2

    def test_reset_creates_new_instance(self):
        bus1 = get_message_bus()
        reset_message_bus()
        bus2 = get_message_bus()
        assert bus1 is not bus2

    def test_reset_clears_subscriptions(self):
        bus = get_message_bus()
        received = []
        bus.subscribe(EventType.MARKET_DATA_REQUEST, received.append)

        reset_message_bus()

        new_bus = get_message_bus()
        new_bus.publish(_make_event())

        assert received == []
