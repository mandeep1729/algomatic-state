package redisbus

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/redis/go-redis/v9"
)

// Handler processes an incoming event.
type Handler func(ctx context.Context, event *Event) error

// Bus wraps a Redis client for pub/sub communication.
type Bus struct {
	client        *redis.Client
	channelPrefix string
	logger        *slog.Logger
}

// NewBus creates a new Redis pub/sub bus.
func NewBus(addr, password string, db int, channelPrefix string, logger *slog.Logger) *Bus {
	if logger == nil {
		logger = slog.Default()
	}

	client := redis.NewClient(&redis.Options{
		Addr:     addr,
		Password: password,
		DB:       db,
	})

	return &Bus{
		client:        client,
		channelPrefix: channelPrefix,
		logger:        logger,
	}
}

// HealthCheck verifies Redis connectivity.
func (b *Bus) HealthCheck(ctx context.Context) error {
	return b.client.Ping(ctx).Err()
}

// Close shuts down the Redis client.
func (b *Bus) Close() error {
	return b.client.Close()
}

// Publish sends an event to the appropriate Redis channel.
func (b *Bus) Publish(ctx context.Context, event *Event) error {
	channel := b.channelFor(event.EventType)
	data, err := event.Marshal()
	if err != nil {
		return fmt.Errorf("marshalling event: %w", err)
	}

	if err := b.client.Publish(ctx, channel, data).Err(); err != nil {
		return fmt.Errorf("publishing to %s: %w", channel, err)
	}

	b.logger.Debug("Published event",
		"event_type", event.EventType,
		"channel", channel,
		"correlation_id", event.CorrelationID,
	)
	return nil
}

// Subscribe listens for events of the given type and calls handler for each.
// Blocks until ctx is cancelled. Returns nil on clean shutdown.
func (b *Bus) Subscribe(ctx context.Context, eventType string, handler Handler) error {
	channel := b.channelFor(eventType)
	pubsub := b.client.Subscribe(ctx, channel)
	defer pubsub.Close()

	b.logger.Info("Subscribed to Redis channel", "channel", channel)

	ch := pubsub.Channel()
	for {
		select {
		case <-ctx.Done():
			b.logger.Info("Unsubscribed from Redis channel", "channel", channel)
			return nil

		case msg, ok := <-ch:
			if !ok {
				b.logger.Warn("Redis subscription channel closed", "channel", channel)
				return nil
			}

			event, err := UnmarshalEvent([]byte(msg.Payload))
			if err != nil {
				b.logger.Error("Failed to unmarshal event",
					"channel", channel,
					"error", err,
					"payload_preview", truncate(msg.Payload, 200),
				)
				continue
			}

			b.logger.Debug("Received event",
				"event_type", event.EventType,
				"correlation_id", event.CorrelationID,
				"source", event.Source,
			)

			if err := handler(ctx, event); err != nil {
				b.logger.Error("Handler failed",
					"event_type", event.EventType,
					"correlation_id", event.CorrelationID,
					"error", err,
				)
			}
		}
	}
}

// channelFor maps an event type to a Redis channel name.
func (b *Bus) channelFor(eventType string) string {
	return b.channelPrefix + ":" + eventType
}

func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}
