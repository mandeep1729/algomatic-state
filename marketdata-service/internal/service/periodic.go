package service

import (
	"context"
	"log/slog"
	"sort"
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
// Merges position symbols and agent symbols from the backend, deduplicates.
// Calls EnsureData to fetch missing 1Min data before aggregation.
func runScan(ctx context.Context, svc *Service, backendURL string, logger *slog.Logger) {
	startTime := time.Now()
	logger.Info("Starting periodic aggregation scan")

	var symbols []string

	if backendURL != "" {
		symbols = mergeSymbols(ctx, backendURL, logger)
	} else {
		var err error
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
	errCount := 0

	scanStart := time.Now().UTC().AddDate(0, 0, -30)
	scanEnd := time.Now().UTC()

	for _, symbol := range symbols {
		select {
		case <-ctx.Done():
			logger.Info("Periodic scan interrupted by shutdown")
			return
		default:
		}

		// Ensure 1Min data exists before aggregating.
		result, err := svc.EnsureData(ctx, symbol, []string{"1Min"}, scanStart, scanEnd)
		if err != nil {
			logger.Warn("EnsureData failed in periodic scan",
				"symbol", symbol,
				"error", err,
			)
			// Continue — we can still try to aggregate whatever 1Min data already exists.
		} else if n, ok := result["1Min"]; ok && n > 0 {
			logger.Info("Fetched new 1Min data in periodic scan",
				"symbol", symbol,
				"bars", n,
			)
		}

		tickerID, err := svc.db.GetOrCreateTicker(ctx, symbol)
		if err != nil {
			logger.Error("Failed to get ticker", "symbol", symbol, "error", err)
			errCount++
			continue
		}

		// Aggregate all timeframes from existing 1Min data.
		aggStart := time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)

		for _, tf := range []string{"15Min", "1Hour"} {
			n, err := svc.aggregateTimeframe(ctx, tickerID, symbol, tf, aggStart, scanEnd)
			if err != nil {
				logger.Error("Aggregation failed in periodic scan",
					"symbol", symbol,
					"timeframe", tf,
					"error", err,
				)
				errCount++
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
		"errors", errCount,
		"elapsed", elapsed.Round(time.Millisecond),
	)
}

// mergeSymbols fetches position symbols and agent symbols, deduplicates and returns sorted.
func mergeSymbols(ctx context.Context, backendURL string, logger *slog.Logger) []string {
	seen := make(map[string]bool)

	posSymbols, err := FetchPositionSymbols(ctx, backendURL)
	if err != nil {
		logger.Warn("Failed to fetch position symbols", "error", err)
	} else {
		for _, s := range posSymbols {
			seen[s] = true
		}
		logger.Info("Fetched position symbols", "count", len(posSymbols))
	}

	agentSymbols, err := FetchAgentSymbols(ctx, backendURL)
	if err != nil {
		logger.Warn("Failed to fetch agent symbols", "error", err)
	} else {
		for _, s := range agentSymbols {
			seen[s] = true
		}
		logger.Info("Fetched agent symbols", "count", len(agentSymbols))
	}

	symbols := make([]string, 0, len(seen))
	for s := range seen {
		symbols = append(symbols, s)
	}

	sort.Strings(symbols)

	logger.Info("Merged symbols for periodic scan",
		"position_count", len(posSymbols),
		"agent_count", len(agentSymbols),
		"merged_count", len(symbols),
	)
	return symbols
}
