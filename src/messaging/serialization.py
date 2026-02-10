"""JSON serialization for events crossing process boundaries (e.g. Redis)."""

import json
import logging
from datetime import datetime, date, timezone

from src.messaging.events import Event, EventType

logger = logging.getLogger(__name__)

_ISO_FMT = "%Y-%m-%dT%H:%M:%S.%f%z"


def event_to_dict(event: Event) -> dict:
    """Convert an ``Event`` to a JSON-compatible dictionary.

    ``datetime`` values inside the payload are converted to ISO-8601 strings.
    """
    return {
        "event_type": event.event_type.value,
        "payload": _serialize_payload(event.payload),
        "source": event.source,
        "timestamp": event.timestamp.isoformat(),
        "correlation_id": event.correlation_id,
    }


def event_to_json(event: Event) -> str:
    """Serialize an ``Event`` to a JSON string."""
    return json.dumps(event_to_dict(event))


def event_from_dict(data: dict) -> Event:
    """Reconstruct an ``Event`` from a dictionary."""
    return Event(
        event_type=EventType(data["event_type"]),
        payload=_deserialize_payload(data.get("payload", {})),
        source=data["source"],
        timestamp=_parse_datetime(data["timestamp"]),
        correlation_id=data["correlation_id"],
    )


def event_from_json(raw: str | bytes) -> Event:
    """Deserialize an ``Event`` from a JSON string."""
    return event_from_dict(json.loads(raw))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _serialize_payload(payload: dict) -> dict:
    """Recursively convert non-JSON-native types in a payload dict."""
    result: dict = {}
    for key, value in payload.items():
        result[key] = _serialize_value(value)
    return result


def _serialize_value(value):
    """Convert a single value to a JSON-safe representation."""
    if isinstance(value, datetime):
        return {"__type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__type__": "date", "value": value.isoformat()}
    if isinstance(value, dict):
        return _serialize_payload(value)
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    return value


def _deserialize_payload(payload: dict) -> dict:
    """Recursively restore typed values in a payload dict."""
    result: dict = {}
    for key, value in payload.items():
        result[key] = _deserialize_value(value)
    return result


def _deserialize_value(value):
    """Restore a single value from its JSON representation."""
    if isinstance(value, dict):
        if value.get("__type__") == "datetime":
            return _parse_datetime(value["value"])
        if value.get("__type__") == "date":
            return date.fromisoformat(value["value"])
        return _deserialize_payload(value)
    if isinstance(value, list):
        return [_deserialize_value(v) for v in value]
    return value


def _parse_datetime(raw: str) -> datetime:
    """Parse an ISO-8601 datetime string, ensuring UTC timezone."""
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
