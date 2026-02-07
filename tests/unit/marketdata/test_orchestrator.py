"""Tests for MarketDataOrchestrator."""

from unittest.mock import MagicMock, patch

import pytest

from src.marketdata.orchestrator import MarketDataOrchestrator
from src.messaging.bus import MessageBus, reset_message_bus
from src.messaging.events import Event, EventType


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_message_bus()
    yield
    reset_message_bus()


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.source_name = "test_provider"
    return provider


@pytest.fixture
def bus():
    return MessageBus()


def _make_request_event(**payload_overrides):
    payload = {
        "symbol": "AAPL",
        "timeframes": ["1Min"],
        "start": None,
        "end": None,
    }
    payload.update(payload_overrides)
    return Event(
        event_type=EventType.MARKET_DATA_REQUEST,
        payload=payload,
        source="test",
        correlation_id="test-corr-123",
    )


# -----------------------------------------------------------------------
# Lifecycle
# -----------------------------------------------------------------------


class TestLifecycle:
    def test_start_subscribes(self, mock_provider, bus):
        orch = MarketDataOrchestrator(mock_provider, message_bus=bus)
        orch.start()

        assert orch._started is True

    def test_start_twice_is_safe(self, mock_provider, bus):
        orch = MarketDataOrchestrator(mock_provider, message_bus=bus)
        orch.start()
        orch.start()  # should log a warning but not raise

        assert orch._started is True

    def test_stop_unsubscribes(self, mock_provider, bus):
        orch = MarketDataOrchestrator(mock_provider, message_bus=bus)
        orch.start()
        orch.stop()

        assert orch._started is False

    def test_stop_without_start_is_safe(self, mock_provider, bus):
        orch = MarketDataOrchestrator(mock_provider, message_bus=bus)
        orch.stop()  # should not raise

    def test_events_not_received_after_stop(self, mock_provider, bus):
        orch = MarketDataOrchestrator(mock_provider, message_bus=bus)
        orch.start()
        orch.stop()

        # Track any UPDATED events
        updated = []
        bus.subscribe(EventType.MARKET_DATA_UPDATED, updated.append)

        bus.publish(_make_request_event())

        # The orchestrator is stopped, so ensure_data should not have been called
        # and no UPDATED events should be published
        assert updated == []


# -----------------------------------------------------------------------
# Request handling — success
# -----------------------------------------------------------------------


class TestHandleRequestSuccess:
    def test_calls_ensure_data(self, mock_provider, bus):
        orch = MarketDataOrchestrator(mock_provider, message_bus=bus)
        orch.start()

        with patch.object(orch.service, "ensure_data", return_value={"1Min": 100}) as mock_ensure:
            bus.publish(_make_request_event())

        mock_ensure.assert_called_once_with("AAPL", ["1Min"], None, None)

    def test_publishes_updated_for_new_bars(self, mock_provider, bus):
        orch = MarketDataOrchestrator(mock_provider, message_bus=bus)
        orch.start()

        updated_events = []
        bus.subscribe(EventType.MARKET_DATA_UPDATED, updated_events.append)

        with patch.object(
            orch.service, "ensure_data", return_value={"1Min": 50, "5Min": 10},
        ):
            bus.publish(_make_request_event(timeframes=["1Min", "5Min"]))

        assert len(updated_events) == 2
        payloads = [e.payload for e in updated_events]
        tfs = {p["timeframe"] for p in payloads}
        assert tfs == {"1Min", "5Min"}

    def test_does_not_publish_updated_for_zero_bars(self, mock_provider, bus):
        orch = MarketDataOrchestrator(mock_provider, message_bus=bus)
        orch.start()

        updated_events = []
        bus.subscribe(EventType.MARKET_DATA_UPDATED, updated_events.append)

        with patch.object(
            orch.service, "ensure_data", return_value={"1Min": 0},
        ):
            bus.publish(_make_request_event())

        assert updated_events == []

    def test_correlation_id_propagated(self, mock_provider, bus):
        orch = MarketDataOrchestrator(mock_provider, message_bus=bus)
        orch.start()

        updated_events = []
        bus.subscribe(EventType.MARKET_DATA_UPDATED, updated_events.append)

        with patch.object(
            orch.service, "ensure_data", return_value={"1Min": 5},
        ):
            bus.publish(_make_request_event())

        assert len(updated_events) == 1
        assert updated_events[0].correlation_id == "test-corr-123"

    def test_updated_event_source_is_orchestrator(self, mock_provider, bus):
        orch = MarketDataOrchestrator(mock_provider, message_bus=bus)
        orch.start()

        updated_events = []
        bus.subscribe(EventType.MARKET_DATA_UPDATED, updated_events.append)

        with patch.object(
            orch.service, "ensure_data", return_value={"1Min": 5},
        ):
            bus.publish(_make_request_event())

        assert updated_events[0].source == "MarketDataOrchestrator"

    def test_updated_payload_contains_new_bars(self, mock_provider, bus):
        orch = MarketDataOrchestrator(mock_provider, message_bus=bus)
        orch.start()

        updated_events = []
        bus.subscribe(EventType.MARKET_DATA_UPDATED, updated_events.append)

        with patch.object(
            orch.service, "ensure_data", return_value={"1Day": 20},
        ):
            bus.publish(_make_request_event(timeframes=["1Day"]))

        assert updated_events[0].payload["new_bars"] == 20
        assert updated_events[0].payload["symbol"] == "AAPL"
        assert updated_events[0].payload["timeframe"] == "1Day"


# -----------------------------------------------------------------------
# Request handling — failure
# -----------------------------------------------------------------------


class TestHandleRequestFailure:
    def test_publishes_failed_on_exception(self, mock_provider, bus):
        orch = MarketDataOrchestrator(mock_provider, message_bus=bus)
        orch.start()

        failed_events = []
        bus.subscribe(EventType.MARKET_DATA_FAILED, failed_events.append)

        with patch.object(
            orch.service, "ensure_data", side_effect=RuntimeError("DB down"),
        ):
            bus.publish(_make_request_event())

        assert len(failed_events) == 1
        assert "DB down" in failed_events[0].payload["error"]

    def test_failed_event_carries_correlation_id(self, mock_provider, bus):
        orch = MarketDataOrchestrator(mock_provider, message_bus=bus)
        orch.start()

        failed_events = []
        bus.subscribe(EventType.MARKET_DATA_FAILED, failed_events.append)

        with patch.object(
            orch.service, "ensure_data", side_effect=RuntimeError("oops"),
        ):
            bus.publish(_make_request_event())

        assert failed_events[0].correlation_id == "test-corr-123"

    def test_failed_event_source_is_orchestrator(self, mock_provider, bus):
        orch = MarketDataOrchestrator(mock_provider, message_bus=bus)
        orch.start()

        failed_events = []
        bus.subscribe(EventType.MARKET_DATA_FAILED, failed_events.append)

        with patch.object(
            orch.service, "ensure_data", side_effect=ValueError("bad"),
        ):
            bus.publish(_make_request_event())

        assert failed_events[0].source == "MarketDataOrchestrator"

    def test_failed_payload_contains_symbol_and_timeframes(self, mock_provider, bus):
        orch = MarketDataOrchestrator(mock_provider, message_bus=bus)
        orch.start()

        failed_events = []
        bus.subscribe(EventType.MARKET_DATA_FAILED, failed_events.append)

        with patch.object(
            orch.service, "ensure_data", side_effect=RuntimeError("x"),
        ):
            bus.publish(_make_request_event(
                symbol="MSFT", timeframes=["1Min", "1Day"],
            ))

        payload = failed_events[0].payload
        assert payload["symbol"] == "MSFT"
        assert payload["timeframes"] == ["1Min", "1Day"]

    def test_no_updated_published_on_failure(self, mock_provider, bus):
        orch = MarketDataOrchestrator(mock_provider, message_bus=bus)
        orch.start()

        updated_events = []
        bus.subscribe(EventType.MARKET_DATA_UPDATED, updated_events.append)

        with patch.object(
            orch.service, "ensure_data", side_effect=RuntimeError("x"),
        ):
            bus.publish(_make_request_event())

        assert updated_events == []


# -----------------------------------------------------------------------
# Integration with default bus
# -----------------------------------------------------------------------


class TestDefaultBus:
    def test_uses_global_bus_by_default(self, mock_provider):
        from src.messaging.bus import get_message_bus

        orch = MarketDataOrchestrator(mock_provider)
        assert orch._bus is get_message_bus()
