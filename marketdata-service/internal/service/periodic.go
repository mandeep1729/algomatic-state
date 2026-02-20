package service

import (
	"context"
	"log/slog"
	"time"
)

// RunPeriodicLoop runs aggregation scans at the given interval.
// If backendURL is set, scans only symbols with open positions.
// If backendURL is empty, falls back to all active tickers.
// Blocks until ctx is cancelled.
func RunPeriodicLoop(ctx context.Context, svc *Service, interval time.Duration, backendURL string, logger *slog.Logger) {
	if logger == nil {
		logger = slog.Default()
	}

	logger.Info("Starting periodic aggregation loop",
		"interval", interval,
		"backend_url_configured", backendURL != "",
	)

	// Run immediately on start, then on ticker.
	runScan(ctx, svc, backendURL, logger)

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			logger.Info("Periodic loop stopped")
			return
		case <-ticker.C:
			runScan(ctx, svc, backendURL, logger)
		}
	}
}

// runScan performs one aggregation scan.
// Uses position symbols from the backend if configured, otherwise all active tickers.
func runScan(ctx context.Context, svc *Service, backendURL string, logger *slog.Logger) {
	startTime := time.Now()
	logger.Info("Starting periodic aggregation scan")

	var symbols []string
	var err error

	if backendURL != "" {
		symbols, err = FetchPositionSymbols(ctx, backendURL)
		if err != nil {
			logger.Warn("Failed to fetch position symbols, skipping scan",
				"error", err,
			)
			return
		}
		logger.Info("Fetched position symbols from backend",
			"count", len(symbols),
		)
	} else {
		symbols, err = svc.db.GetActiveTickers(ctx)
		if err != nil {
			logger.Error("Failed to get active tickers", "error", err)
			return
		}
	}

	if len(symbols) == 0 {
		logger.Debug("No tickers to process")
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

		for _, tf := range []string{"15Min", "1Hour"} {
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
