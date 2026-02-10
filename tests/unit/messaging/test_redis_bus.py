"""Tests for RedisMessageBus using mocked Redis connections."""

import threading
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.messaging.bus import InMemoryMessageBus, get_message_bus, reset_message_bus
from src.messaging.base import MessageBusBase
from src.messaging.events import Event, EventType
from src.messaging.serialization import event_to_json, event_from_json


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure a clean singleton for every test."""
    reset_message_bus()
    yield
    reset_message_bus()


def _make_event(event_type=EventType.MARKET_DATA_REQUEST, **overrides):
    defaults = dict(event_type=event_type, payload={"symbol": "AAPL"}, source="test")
    defaults.update(overrides)
    return Event(**defaults)


class TestRedisMessageBusLocalDispatch:
    """Test that RedisMessageBus dispatches locally even when Redis publish fails."""

    @patch("src.messaging.redis_bus.RedisMessageBus._create_pool")
    @patch("src.messaging.redis_bus.RedisMessageBus._get_connection")
    @patch("src.messaging.redis_bus.RedisMessageBus._start_listener")
    def test_local_subscribers_called_on_publish(self, mock_listener, mock_conn, mock_pool):
        """Local subscribers should be called synchronously on publish."""
        mock_redis = MagicMock()
        mock_conn.return_value = mock_redis
        mock_pool.return_value = MagicMock()

        from src.messaging.redis_bus import RedisMessageBus
        bus = RedisMessageBus()

        received = []
        bus.subscribe(EventType.MARKET_DATA_REQUEST, received.append)

        event = _make_event()
        bus.publish(event)

        assert len(received) == 1
        assert received[0] is event

    @patch("src.messaging.redis_bus.RedisMessageBus._create_pool")
    @patch("src.messaging.redis_bus.RedisMessageBus._get_connection")
    @patch("src.messaging.redis_bus.RedisMessageBus._start_listener")
    def test_publish_to_redis(self, mock_listener, mock_conn, mock_pool):
        """Events should be published to Redis after local dispatch."""
        mock_redis = MagicMock()
        mock_conn.return_value = mock_redis
        mock_pool.return_value = MagicMock()

        from src.messaging.redis_bus import RedisMessageBus
        bus = RedisMessageBus()

        event = _make_event()
        bus.publish(event)

        # Redis publish should have been called
        mock_redis.publish.assert_called_once()
        channel, message = mock_redis.publish.call_args[0]
        assert "market_data_request" in channel
        # Verify the message is valid JSON
        restored = event_from_json(message)
        assert restored.correlation_id == event.correlation_id

    @patch("src.messaging.redis_bus.RedisMessageBus._create_pool")
    @patch("src.messaging.redis_bus.RedisMessageBus._get_connection")
    @patch("src.messaging.redis_bus.RedisMessageBus._start_listener")
    def test_local_dispatch_on_redis_failure(self, mock_listener, mock_conn, mock_pool):
        """Local subscribers should still be called if Redis publish fails."""
        mock_redis = MagicMock()
        mock_redis.publish.side_effect = ConnectionError("Redis down")
        mock_conn.return_value = mock_redis
        mock_pool.return_value = MagicMock()

        from src.messaging.redis_bus import RedisMessageBus
        bus = RedisMessageBus()

        received = []
        bus.subscribe(EventType.MARKET_DATA_REQUEST, received.append)

        event = _make_event()
        bus.publish(event)

        # Local subscriber called despite Redis failure
        assert len(received) == 1

    @patch("src.messaging.redis_bus.RedisMessageBus._create_pool")
    @patch("src.messaging.redis_bus.RedisMessageBus._get_connection")
    @patch("src.messaging.redis_bus.RedisMessageBus._start_listener")
    def test_unsubscribe(self, mock_listener, mock_conn, mock_pool):
        """Unsubscribed callbacks should not be called."""
        mock_redis = MagicMock()
        mock_conn.return_value = mock_redis
        mock_pool.return_value = MagicMock()

        from src.messaging.redis_bus import RedisMessageBus
        bus = RedisMessageBus()

        received = []
        bus.subscribe(EventType.MARKET_DATA_REQUEST, received.append)
        bus.unsubscribe(EventType.MARKET_DATA_REQUEST, received.append)

        bus.publish(_make_event())
        assert received == []


class TestRedisMessageBusHealthCheck:
    """Health check tests."""

    @patch("src.messaging.redis_bus.RedisMessageBus._create_pool")
    @patch("src.messaging.redis_bus.RedisMessageBus._get_connection")
    @patch("src.messaging.redis_bus.RedisMessageBus._start_listener")
    def test_health_check_success(self, mock_listener, mock_conn, mock_pool):
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_conn.return_value = mock_redis
        mock_pool.return_value = MagicMock()

        from src.messaging.redis_bus import RedisMessageBus
        bus = RedisMessageBus()

        assert bus.health_check() is True

    @patch("src.messaging.redis_bus.RedisMessageBus._create_pool")
    @patch("src.messaging.redis_bus.RedisMessageBus._get_connection")
    @patch("src.messaging.redis_bus.RedisMessageBus._start_listener")
    def test_health_check_failure(self, mock_listener, mock_conn, mock_pool):
        mock_redis = MagicMock()
        mock_redis.ping.side_effect = ConnectionError("Redis down")
        mock_conn.return_value = mock_redis
        mock_pool.return_value = MagicMock()

        from src.messaging.redis_bus import RedisMessageBus
        bus = RedisMessageBus()

        assert bus.health_check() is False


class TestRedisMessageBusShutdown:
    """Shutdown and cleanup tests."""

    @patch("src.messaging.redis_bus.RedisMessageBus._create_pool")
    @patch("src.messaging.redis_bus.RedisMessageBus._get_connection")
    @patch("src.messaging.redis_bus.RedisMessageBus._start_listener")
    def test_shutdown_sets_event(self, mock_listener, mock_conn, mock_pool):
        mock_redis = MagicMock()
        mock_conn.return_value = mock_redis
        mock_pool.return_value = MagicMock()

        from src.messaging.redis_bus import RedisMessageBus
        bus = RedisMessageBus()

        bus.shutdown()
        assert bus._shutdown_event.is_set()


class TestRedisMessageBusPublishAndWait:
    """publish_and_wait tests with mocked Redis."""

    @patch("src.messaging.redis_bus.RedisMessageBus._create_pool")
    @patch("src.messaging.redis_bus.RedisMessageBus._get_connection")
    @patch("src.messaging.redis_bus.RedisMessageBus._start_listener")
    def test_returns_matching_response(self, mock_listener, mock_conn, mock_pool):
        mock_redis = MagicMock()
        mock_conn.return_value = mock_redis
        mock_pool.return_value = MagicMock()

        from src.messaging.redis_bus import RedisMessageBus
        bus = RedisMessageBus()

        request = _make_event(EventType.INDICATOR_COMPUTE_REQUEST)

        # Responder subscribes to requests
        def responder(event: Event) -> None:
            bus.publish(Event(
                event_type=EventType.INDICATOR_COMPUTE_COMPLETE,
                payload={"bars_computed": 100},
                source="responder",
                correlation_id=event.correlation_id,
            ))

        bus.subscribe(EventType.INDICATOR_COMPUTE_REQUEST, responder)

        response = bus.publish_and_wait(
            request,
            EventType.INDICATOR_COMPUTE_COMPLETE,
            timeout=5.0,
        )

        assert response is not None
        assert response.correlation_id == request.correlation_id
        assert response.payload["bars_computed"] == 100

    @patch("src.messaging.redis_bus.RedisMessageBus._create_pool")
    @patch("src.messaging.redis_bus.RedisMessageBus._get_connection")
    @patch("src.messaging.redis_bus.RedisMessageBus._start_listener")
    def test_timeout_returns_none(self, mock_listener, mock_conn, mock_pool):
        mock_redis = MagicMock()
        mock_conn.return_value = mock_redis
        mock_pool.return_value = MagicMock()

        from src.messaging.redis_bus import RedisMessageBus
        bus = RedisMessageBus()

        request = _make_event(EventType.INDICATOR_COMPUTE_REQUEST)

        response = bus.publish_and_wait(
            request,
            EventType.INDICATOR_COMPUTE_COMPLETE,
            timeout=0.1,
        )

        assert response is None


class TestSelfPublishedTracking:
    """Test that self-published messages are tracked to avoid double-dispatch."""

    @patch("src.messaging.redis_bus.RedisMessageBus._create_pool")
    @patch("src.messaging.redis_bus.RedisMessageBus._get_connection")
    @patch("src.messaging.redis_bus.RedisMessageBus._start_listener")
    def test_self_published_tracked(self, mock_listener, mock_conn, mock_pool):
        mock_redis = MagicMock()
        mock_conn.return_value = mock_redis
        mock_pool.return_value = MagicMock()

        from src.messaging.redis_bus import RedisMessageBus
        bus = RedisMessageBus()

        event = _make_event()
        bus.publish(event)

        assert event.correlation_id in bus._self_published

    @patch("src.messaging.redis_bus.RedisMessageBus._create_pool")
    @patch("src.messaging.redis_bus.RedisMessageBus._get_connection")
    @patch("src.messaging.redis_bus.RedisMessageBus._start_listener")
    def test_handle_redis_message_skips_self(self, mock_listener, mock_conn, mock_pool):
        """Messages we published ourselves should be skipped by the listener."""
        mock_redis = MagicMock()
        mock_conn.return_value = mock_redis
        mock_pool.return_value = MagicMock()

        from src.messaging.redis_bus import RedisMessageBus
        bus = RedisMessageBus()

        received = []
        bus.subscribe(EventType.MARKET_DATA_REQUEST, received.append)

        # Publish an event (adds to _self_published)
        event = _make_event()
        bus.publish(event)
        assert len(received) == 1  # Local dispatch

        # Simulate receiving the same event back from Redis
        redis_message = {
            "type": "message",
            "channel": f"algomatic:market_data_request",
            "data": event_to_json(event),
        }
        bus._handle_redis_message(redis_message)

        # Should NOT have been dispatched again
        assert len(received) == 1

    @patch("src.messaging.redis_bus.RedisMessageBus._create_pool")
    @patch("src.messaging.redis_bus.RedisMessageBus._get_connection")
    @patch("src.messaging.redis_bus.RedisMessageBus._start_listener")
    def test_handle_redis_message_dispatches_foreign(self, mock_listener, mock_conn, mock_pool):
        """Messages from other processes should be dispatched locally."""
        mock_redis = MagicMock()
        mock_conn.return_value = mock_redis
        mock_pool.return_value = MagicMock()

        from src.messaging.redis_bus import RedisMessageBus
        bus = RedisMessageBus()

        received = []
        bus.subscribe(EventType.MARKET_DATA_UPDATED, received.append)

        # Simulate a message from another process
        foreign_event = _make_event(
            event_type=EventType.MARKET_DATA_UPDATED,
            source="other-process",
        )
        redis_message = {
            "type": "message",
            "channel": f"algomatic:market_data_updated",
            "data": event_to_json(foreign_event),
        }
        bus._handle_redis_message(redis_message)

        assert len(received) == 1
        assert received[0].source == "other-process"


class TestFactoryBackendSelection:
    """Test that get_message_bus() respects config."""

    def test_default_is_memory(self):
        bus = get_message_bus()
        assert isinstance(bus, InMemoryMessageBus)

    @patch("config.settings.get_settings")
    def test_memory_backend(self, mock_settings):
        mock_settings.return_value.messaging.backend = "memory"
        reset_message_bus()
        bus = get_message_bus()
        assert isinstance(bus, InMemoryMessageBus)
