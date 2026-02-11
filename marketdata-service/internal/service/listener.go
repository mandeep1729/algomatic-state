package service

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/algomatic/marketdata-service/internal/redisbus"
)

// RunListener subscribes to market_data_request events and processes them.
// Blocks until ctx is cancelled.
func RunListener(ctx context.Context, svc *Service, bus *redisbus.Bus, logger *slog.Logger) error {
	if logger == nil {
		logger = slog.Default()
	}

	logger.Info("Starting market data listener")

	return bus.Subscribe(ctx, redisbus.EventMarketDataRequest, func(ctx context.Context, event *redisbus.Event) error {
		return handleRequest(ctx, svc, bus, event, logger)
	})
}

func handleRequest(ctx context.Context, svc *Service, bus *redisbus.Bus, event *redisbus.Event, logger *slog.Logger) error {
	symbol, _ := event.Payload["symbol"].(string)
	if symbol == "" {
		logger.Warn("Received request with empty symbol",
			"correlation_id", event.CorrelationID,
		)
		return nil
	}

	// Parse timeframes.
	var timeframes []string
	if raw, ok := event.Payload["timeframes"]; ok {
		if arr, ok := raw.([]any); ok {
			for _, v := range arr {
				if s, ok := v.(string); ok {
					timeframes = append(timeframes, s)
				}
			}
		}
	}
	if len(timeframes) == 0 {
		timeframes = []string{"1Min", "5Min", "15Min", "1Hour", "1Day"}
	}

	// Parse start/end times.
	start := time.Now().AddDate(0, 0, -30) // Default: 30 days back.
	end := time.Now()

	if v, ok := event.Payload["start"]; ok && v != nil {
		if t, err := redisbus.ParsePayloadTime(v); err == nil {
			start = t
		}
	}
	if v, ok := event.Payload["end"]; ok && v != nil {
		if t, err := redisbus.ParsePayloadTime(v); err == nil {
			end = t
		}
	}

	logger.Info("Processing market data request",
		"symbol", symbol,
		"timeframes", timeframes,
		"correlation_id", event.CorrelationID,
		"source", event.Source,
	)

	result, err := svc.EnsureData(ctx, symbol, timeframes, start, end)
	if err != nil {
		logger.Error("EnsureData failed",
			"symbol", symbol,
			"error", err,
			"correlation_id", event.CorrelationID,
		)

		// Publish failure event.
		errMsg := err.Error()
		return bus.Publish(ctx, &redisbus.Event{
			EventType: redisbus.EventMarketDataFailed,
			Payload: map[string]any{
				"symbol":     symbol,
				"timeframes": timeframes,
				"error":      errMsg,
			},
			Source:        "marketdata-service-go",
			Timestamp:     time.Now().UTC(),
			CorrelationID: event.CorrelationID,
		})
	}

	// Publish success events for each timeframe that has new bars.
	for tf, newBars := range result {
		if newBars > 0 {
			if pubErr := bus.Publish(ctx, &redisbus.Event{
				EventType: redisbus.EventMarketDataUpdated,
				Payload: map[string]any{
					"symbol":    symbol,
					"timeframe": tf,
					"new_bars":  newBars,
				},
				Source:        "marketdata-service-go",
				Timestamp:     time.Now().UTC(),
				CorrelationID: event.CorrelationID,
			}); pubErr != nil {
				logger.Error("Failed to publish update event",
					"symbol", symbol,
					"timeframe", tf,
					"error", pubErr,
				)
			}
		}
	}

	logger.Info("Request handled successfully",
		"symbol", symbol,
		"result", fmt.Sprintf("%v", result),
		"correlation_id", event.CorrelationID,
	)
	return nil
}
