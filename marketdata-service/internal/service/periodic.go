package service

import (
	"context"
	"log/slog"
	"sort"
	"time"
)

// RunPeriodicLoop runs periodic data scans at the given interval.
// If backendURL is set, scans only symbols with open positions.
// If backendURL is empty, falls back to all active tickers.
// Blocks until ctx is cancelled.
func RunPeriodicLoop(ctx context.Context, svc *Service, interval time.Duration, backendURL string, logger *slog.Logger) {
	if logger == nil {
		logger = slog.Default()
	}

	logger.Info("Starting periodic data loop",
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

// runScan performs one periodic data scan.
// Merges position symbols and agent symbols from the backend, deduplicates.
// Calls EnsureData to fetch 1Min (source for continuous aggregates) and 1Day data.
func runScan(ctx context.Context, svc *Service, backendURL string, logger *slog.Logger) {
	startTime := time.Now()
	logger.Info("Starting periodic data scan")

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

	processed := 0

	scanStart := time.Now().UTC().AddDate(0, 0, -30)
	scanEnd := time.Now().UTC()

	for _, symbol := range symbols {
		select {
		case <-ctx.Done():
			logger.Info("Periodic scan interrupted by shutdown")
			return
		default:
		}

		// Fetch 1Min (source for continuous aggregates) and 1Day (separate Alpaca query).
		// 5Min, 15Min, 1Hour are auto-computed by TimescaleDB continuous aggregates from 1Min.
		result, err := svc.EnsureData(ctx, symbol, []string{"1Min", "1Day"}, scanStart, scanEnd)
		if err != nil {
			logger.Warn("EnsureData failed in periodic scan",
				"symbol", symbol,
				"error", err,
			)
		} else {
			if n, ok := result["1Min"]; ok && n > 0 {
				logger.Info("Fetched new 1Min data", "symbol", symbol, "bars", n)
			}
			if n, ok := result["1Day"]; ok && n > 0 {
				logger.Info("Fetched new 1Day data", "symbol", symbol, "bars", n)
			}
		}
		processed++
	}

	elapsed := time.Since(startTime)
	logger.Info("Periodic scan complete",
		"tickers_processed", processed,
		"total_tickers", len(symbols),
		"elapsed", elapsed.Round(time.Millisecond),
	)
}

// symbolSource defines a named symbol fetcher for the periodic scan.
type symbolSource struct {
	name  string
	fetch func(ctx context.Context, backendURL string) ([]string, error)
}

// mergeSymbols fetches symbols from all sources, deduplicates and returns sorted.
// Sources: open positions, active agents, user favorites, recent trades (7 days).
func mergeSymbols(ctx context.Context, backendURL string, logger *slog.Logger) []string {
	sources := []symbolSource{
		{"positions", FetchPositionSymbols},
		{"agents", FetchAgentSymbols},
		{"favorites", FetchFavoriteSymbols},
		{"recent_trades", FetchRecentTradeSymbols},
	}

	seen := make(map[string]bool)
	counts := make(map[string]int, len(sources))

	for _, src := range sources {
		syms, err := src.fetch(ctx, backendURL)
		if err != nil {
			logger.Warn("Failed to fetch symbols", "source", src.name, "error", err)
			continue
		}
		for _, s := range syms {
			seen[s] = true
		}
		counts[src.name] = len(syms)
		logger.Info("Fetched symbols", "source", src.name, "count", len(syms))
	}

	symbols := make([]string, 0, len(seen))
	for s := range seen {
		symbols = append(symbols, s)
	}

	sort.Strings(symbols)

	logger.Info("Merged symbols for periodic scan",
		"position_count", counts["positions"],
		"agent_count", counts["agents"],
		"favorite_count", counts["favorites"],
		"recent_trade_count", counts["recent_trades"],
		"merged_count", len(symbols),
	)
	return symbols
}
