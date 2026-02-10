"""Tests for event JSON serialization and deserialization."""

import json
from datetime import datetime, date, timezone, timedelta

import pytest

from src.messaging.events import Event, EventType
from src.messaging.serialization import (
    event_to_dict,
    event_to_json,
    event_from_dict,
    event_from_json,
)


def _make_event(**overrides):
    defaults = dict(
        event_type=EventType.MARKET_DATA_REQUEST,
        payload={"symbol": "AAPL"},
        source="test",
        timestamp=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        correlation_id="test-id-123",
    )
    defaults.update(overrides)
    return Event(**defaults)


class TestEventToDict:
    """Serialize Event to dict."""

    def test_basic_roundtrip(self):
        event = _make_event()
        d = event_to_dict(event)

        assert d["event_type"] == "market_data_request"
        assert d["source"] == "test"
        assert d["correlation_id"] == "test-id-123"
        assert isinstance(d["timestamp"], str)
        assert d["payload"]["symbol"] == "AAPL"

    def test_all_event_types(self):
        for et in EventType:
            event = _make_event(event_type=et)
            d = event_to_dict(event)
            assert d["event_type"] == et.value

    def test_dict_is_json_serializable(self):
        event = _make_event()
        d = event_to_dict(event)
        # Should not raise
        json.dumps(d)


class TestPayloadDatetimeSerialization:
    """Datetime values inside payloads must be preserved."""

    def test_datetime_in_payload(self):
        dt = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        event = _make_event(payload={"start": dt, "symbol": "SPY"})
        d = event_to_dict(event)

        assert d["payload"]["start"]["__type__"] == "datetime"
        assert "2024-03-15" in d["payload"]["start"]["value"]
        assert d["payload"]["symbol"] == "SPY"

    def test_date_in_payload(self):
        d_val = date(2024, 3, 15)
        event = _make_event(payload={"date": d_val})
        d = event_to_dict(event)

        assert d["payload"]["date"]["__type__"] == "date"
        assert d["payload"]["date"]["value"] == "2024-03-15"

    def test_nested_datetime(self):
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        event = _make_event(payload={"nested": {"ts": dt}})
        d = event_to_dict(event)

        assert d["payload"]["nested"]["ts"]["__type__"] == "datetime"

    def test_list_with_datetime(self):
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        event = _make_event(payload={"times": [dt, "other"]})
        d = event_to_dict(event)

        assert d["payload"]["times"][0]["__type__"] == "datetime"
        assert d["payload"]["times"][1] == "other"


class TestEventFromDict:
    """Deserialize dict back to Event."""

    def test_basic_roundtrip(self):
        original = _make_event()
        d = event_to_dict(original)
        restored = event_from_dict(d)

        assert restored.event_type == original.event_type
        assert restored.source == original.source
        assert restored.correlation_id == original.correlation_id
        assert restored.payload["symbol"] == "AAPL"
        assert restored.timestamp == original.timestamp

    def test_datetime_payload_roundtrip(self):
        dt = datetime(2024, 6, 1, 15, 30, 0, tzinfo=timezone.utc)
        original = _make_event(payload={"start": dt, "end": dt + timedelta(days=30)})
        d = event_to_dict(original)
        restored = event_from_dict(d)

        assert isinstance(restored.payload["start"], datetime)
        assert restored.payload["start"] == dt
        assert restored.payload["end"] == dt + timedelta(days=30)

    def test_date_payload_roundtrip(self):
        d_val = date(2024, 12, 25)
        original = _make_event(payload={"date": d_val})
        d = event_to_dict(original)
        restored = event_from_dict(d)

        assert isinstance(restored.payload["date"], date)
        assert restored.payload["date"] == d_val

    def test_all_event_types_roundtrip(self):
        for et in EventType:
            original = _make_event(event_type=et)
            restored = event_from_dict(event_to_dict(original))
            assert restored.event_type == et


class TestEventJsonString:
    """Full JSON string round-trip."""

    def test_json_roundtrip(self):
        original = _make_event(
            payload={
                "symbol": "TSLA",
                "timeframes": ["1Min", "5Min"],
                "start": datetime(2024, 1, 1, tzinfo=timezone.utc),
            }
        )
        json_str = event_to_json(original)
        restored = event_from_json(json_str)

        assert restored.event_type == original.event_type
        assert restored.source == original.source
        assert restored.correlation_id == original.correlation_id
        assert restored.payload["symbol"] == "TSLA"
        assert restored.payload["timeframes"] == ["1Min", "5Min"]
        assert isinstance(restored.payload["start"], datetime)

    def test_json_roundtrip_bytes(self):
        original = _make_event()
        json_bytes = event_to_json(original).encode("utf-8")
        restored = event_from_json(json_bytes)
        assert restored.event_type == original.event_type

    def test_indicator_compute_events(self):
        for et in [
            EventType.INDICATOR_COMPUTE_REQUEST,
            EventType.INDICATOR_COMPUTE_COMPLETE,
            EventType.INDICATOR_COMPUTE_FAILED,
        ]:
            original = _make_event(
                event_type=et,
                payload={"symbol": "AAPL", "timeframe": "5Min"},
            )
            restored = event_from_json(event_to_json(original))
            assert restored.event_type == et
            assert restored.payload["timeframe"] == "5Min"


class TestEventToDictFromDictMethods:
    """Test the to_dict/from_dict methods on Event itself."""

    def test_to_dict(self):
        event = _make_event()
        d = event.to_dict()
        assert d["event_type"] == "market_data_request"

    def test_from_dict(self):
        event = _make_event()
        d = event.to_dict()
        restored = Event.from_dict(d)
        assert restored.event_type == event.event_type
        assert restored.correlation_id == event.correlation_id
