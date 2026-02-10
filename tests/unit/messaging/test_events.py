"""Tests for Event and EventType."""

from datetime import datetime, timezone

import pytest

from src.messaging.events import Event, EventType


class TestEventType:
    """Tests for the EventType enum."""

    def test_request_value(self):
        assert EventType.MARKET_DATA_REQUEST.value == "market_data_request"

    def test_updated_value(self):
        assert EventType.MARKET_DATA_UPDATED.value == "market_data_updated"

    def test_failed_value(self):
        assert EventType.MARKET_DATA_FAILED.value == "market_data_failed"

    def test_all_members(self):
        assert len(EventType) == 6


class TestEvent:
    """Tests for the Event frozen dataclass."""

    def test_create_minimal(self):
        event = Event(
            event_type=EventType.MARKET_DATA_REQUEST,
            payload={"symbol": "AAPL"},
            source="test",
        )
        assert event.event_type == EventType.MARKET_DATA_REQUEST
        assert event.payload == {"symbol": "AAPL"}
        assert event.source == "test"

    def test_timestamp_auto_generated(self):
        event = Event(
            event_type=EventType.MARKET_DATA_REQUEST,
            payload={},
            source="test",
        )
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo is not None

    def test_correlation_id_auto_generated(self):
        event = Event(
            event_type=EventType.MARKET_DATA_REQUEST,
            payload={},
            source="test",
        )
        assert isinstance(event.correlation_id, str)
        assert len(event.correlation_id) > 0

    def test_unique_correlation_ids(self):
        e1 = Event(event_type=EventType.MARKET_DATA_REQUEST, payload={}, source="a")
        e2 = Event(event_type=EventType.MARKET_DATA_REQUEST, payload={}, source="a")
        assert e1.correlation_id != e2.correlation_id

    def test_explicit_correlation_id(self):
        event = Event(
            event_type=EventType.MARKET_DATA_UPDATED,
            payload={},
            source="test",
            correlation_id="my-id-123",
        )
        assert event.correlation_id == "my-id-123"

    def test_explicit_timestamp(self):
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        event = Event(
            event_type=EventType.MARKET_DATA_FAILED,
            payload={},
            source="test",
            timestamp=ts,
        )
        assert event.timestamp == ts

    def test_frozen_cannot_mutate(self):
        event = Event(
            event_type=EventType.MARKET_DATA_REQUEST,
            payload={},
            source="test",
        )
        with pytest.raises(AttributeError):
            event.source = "other"

    def test_payload_can_hold_complex_data(self):
        payload = {
            "symbol": "AAPL",
            "timeframes": ["1Min", "5Min"],
            "start": datetime(2024, 1, 1),
            "nested": {"key": [1, 2, 3]},
        }
        event = Event(
            event_type=EventType.MARKET_DATA_REQUEST,
            payload=payload,
            source="test",
        )
        assert event.payload["timeframes"] == ["1Min", "5Min"]
        assert event.payload["nested"]["key"] == [1, 2, 3]
