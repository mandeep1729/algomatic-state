package service

import (
	"context"
	"log/slog"
	"time"
)

// RunPeriodicLoop runs aggregation scans at the given interval.
// Blocks until ctx is cancelled.
func RunPeriodicLoop(ctx context.Context, svc *Service, interval time.Duration, logger *slog.Logger) {
	if logger == nil {
		logger = slog.Default()
	}

	logger.Info("Starting periodic aggregation loop",
		"interval", interval,
	)

	// Run immediately on start, then on ticker.
	runScan(ctx, svc, logger)

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			logger.Info("Periodic loop stopped")
			return
		case <-ticker.C:
			runScan(ctx, svc, logger)
		}
	}
}

// runScan performs one aggregation scan across all active tickers.
func runScan(ctx context.Context, svc *Service, logger *slog.Logger) {
	startTime := time.Now()
	logger.Info("Starting periodic aggregation scan")

	symbols, err := svc.db.GetActiveTickers(ctx)
	if err != nil {
		logger.Error("Failed to get active tickers", "error", err)
		return
	}

	if len(symbols) == 0 {
		logger.Debug("No active tickers to process")
		return
	}

	totalBars := 0
	processed := 0
	errors := 0

	for _, symbol := range symbols {
		select {
		case <-ctx.Done():
			logger.Info("Periodic scan interrupted by shutdown")
			return
		default:
		}

		tickerID, err := svc.db.GetOrCreateTicker(ctx, symbol)
		if err != nil {
			logger.Error("Failed to get ticker", "symbol", symbol, "error", err)
			errors++
			continue
		}

		// Aggregate all timeframes from existing 1Min data.
		// Use a wide time range — the aggregator will pick up from the last aggregated bar.
		scanStart := time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)
		scanEnd := time.Now().UTC()

		for _, tf := range []string{"5Min", "15Min", "1Hour"} {
			n, err := svc.aggregateTimeframe(ctx, tickerID, symbol, tf, scanStart, scanEnd)
			if err != nil {
				logger.Error("Aggregation failed in periodic scan",
					"symbol", symbol,
					"timeframe", tf,
					"error", err,
				)
				errors++
				continue
			}
			totalBars += n
		}
		processed++
	}

	elapsed := time.Since(startTime)
	logger.Info("Periodic aggregation scan complete",
		"tickers_processed", processed,
		"total_tickers", len(symbols),
		"total_bars_aggregated", totalBars,
		"errors", errors,
		"elapsed", elapsed.Round(time.Millisecond),
	)
}
