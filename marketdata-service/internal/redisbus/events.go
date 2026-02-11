package redisbus

import (
	"encoding/json"
	"fmt"
	"time"
)

// Event type constants matching Python EventType enum values.
const (
	EventMarketDataRequest = "market_data_request"
	EventMarketDataUpdated = "market_data_updated"
	EventMarketDataFailed  = "market_data_failed"
)

// Event represents a message flowing through the Redis bus.
// Structure matches the Python Event dataclass serialization format.
type Event struct {
	EventType     string         `json:"event_type"`
	Payload       map[string]any `json:"payload"`
	Source        string         `json:"source"`
	Timestamp     time.Time      `json:"timestamp"`
	CorrelationID string         `json:"correlation_id"`
}

// Marshal serializes an event to JSON.
func (e *Event) Marshal() ([]byte, error) {
	// Convert to the wire format that matches Python serialization.
	wire := map[string]any{
		"event_type":     e.EventType,
		"payload":        serializePayload(e.Payload),
		"source":         e.Source,
		"timestamp":      e.Timestamp.Format(time.RFC3339Nano),
		"correlation_id": e.CorrelationID,
	}
	return json.Marshal(wire)
}

// UnmarshalEvent deserializes an event from JSON bytes.
func UnmarshalEvent(data []byte) (*Event, error) {
	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("unmarshalling event JSON: %w", err)
	}

	eventType, _ := raw["event_type"].(string)
	source, _ := raw["source"].(string)
	correlationID, _ := raw["correlation_id"].(string)

	tsStr, _ := raw["timestamp"].(string)
	ts, err := parseTimestamp(tsStr)
	if err != nil {
		return nil, fmt.Errorf("parsing event timestamp: %w", err)
	}

	payloadRaw, _ := raw["payload"].(map[string]any)
	payload := deserializePayload(payloadRaw)

	return &Event{
		EventType:     eventType,
		Payload:       payload,
		Source:        source,
		Timestamp:     ts,
		CorrelationID: correlationID,
	}, nil
}

// ParsePayloadTime extracts a time.Time from a payload value.
// Handles both ISO string and Python {"__type__": "datetime", "value": "..."} format.
func ParsePayloadTime(v any) (time.Time, error) {
	switch val := v.(type) {
	case string:
		return parseTimestamp(val)
	case map[string]any:
		if val["__type__"] == "datetime" {
			if s, ok := val["value"].(string); ok {
				return parseTimestamp(s)
			}
		}
		if val["__type__"] == "date" {
			if s, ok := val["value"].(string); ok {
				return time.Parse("2006-01-02", s)
			}
		}
	}
	return time.Time{}, fmt.Errorf("cannot parse time from %T: %v", v, v)
}

// parseTimestamp tries multiple timestamp formats.
func parseTimestamp(s string) (time.Time, error) {
	formats := []string{
		time.RFC3339Nano,
		time.RFC3339,
		"2006-01-02T15:04:05.999999+00:00",
		"2006-01-02T15:04:05",
		"2006-01-02 15:04:05",
		"2006-01-02",
	}
	for _, f := range formats {
		t, err := time.Parse(f, s)
		if err == nil {
			return t.UTC(), nil
		}
	}
	return time.Time{}, fmt.Errorf("unrecognised timestamp format: %s", s)
}

// serializePayload converts Go types to the Python-compatible wire format.
func serializePayload(payload map[string]any) map[string]any {
	if payload == nil {
		return nil
	}
	result := make(map[string]any, len(payload))
	for k, v := range payload {
		result[k] = serializeValue(v)
	}
	return result
}

func serializeValue(v any) any {
	switch val := v.(type) {
	case time.Time:
		return map[string]any{
			"__type__": "datetime",
			"value":    val.Format(time.RFC3339Nano),
		}
	case map[string]any:
		return serializePayload(val)
	case []any:
		out := make([]any, len(val))
		for i, item := range val {
			out[i] = serializeValue(item)
		}
		return out
	default:
		return v
	}
}

// deserializePayload restores typed values from the wire format.
func deserializePayload(payload map[string]any) map[string]any {
	if payload == nil {
		return nil
	}
	result := make(map[string]any, len(payload))
	for k, v := range payload {
		result[k] = deserializeValue(v)
	}
	return result
}

func deserializeValue(v any) any {
	switch val := v.(type) {
	case map[string]any:
		if val["__type__"] == "datetime" {
			if s, ok := val["value"].(string); ok {
				if t, err := parseTimestamp(s); err == nil {
					return t
				}
			}
		}
		if val["__type__"] == "date" {
			if s, ok := val["value"].(string); ok {
				if t, err := time.Parse("2006-01-02", s); err == nil {
					return t
				}
			}
		}
		return deserializePayload(val)
	case []any:
		out := make([]any, len(val))
		for i, item := range val {
			out[i] = deserializeValue(item)
		}
		return out
	default:
		return v
	}
}
