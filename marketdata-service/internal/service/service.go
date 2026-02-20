package service

import (
	"context"
	"fmt"
	"log/slog"
	"sync"
	"time"

	"github.com/algomatic/marketdata-service/internal/aggregator"
	"github.com/algomatic/marketdata-service/internal/alpaca"
	"github.com/algomatic/marketdata-service/internal/db"
)

// DBClient abstracts database operations so both db.Client (direct pgx)
// and dataclient.Client (gRPC) can be used.
type DBClient interface {
	GetOrCreateTicker(ctx context.Context, symbol string) (int, error)
	GetActiveTickers(ctx context.Context) ([]string, error)
	GetLatestTimestamp(ctx context.Context, tickerID int, timeframe string) (*time.Time, error)
	GetBars1Min(ctx context.Context, tickerID int, after time.Time) ([]db.OHLCVBar, error)
	BulkInsertBars(ctx context.Context, tickerID int, timeframe, source string, bars []db.OHLCVBar) (int, error)
	UpdateSyncLog(ctx context.Context, entry db.SyncLogEntry) error
	DeactivateTicker(ctx context.Context, symbol string) error
	HealthCheck(ctx context.Context) error
}

// pendingRequest tracks in-flight requests for request coalescing.
type pendingRequest struct {
	done   chan struct{}
	result map[string]int
	err    error
}

// Service orchestrates market data fetching and aggregation.
type Service struct {
	db     DBClient
	alpaca *alpaca.Client
	logger *slog.Logger

	// Request coalescing: concurrent requests for the same symbol share one fetch.
	pending sync.Map // map[string]*pendingRequest
}

// NewService creates a new market data service.
func NewService(dbClient DBClient, alpacaClient *alpaca.Client, logger *slog.Logger) *Service {
	if logger == nil {
		logger = slog.Default()
	}
	return &Service{
		db:     dbClient,
		alpaca: alpacaClient,
		logger: logger,
	}
}

// EnsureData ensures bars exist in the database for the given symbol, timeframes, and range.
// Uses request coalescing — concurrent calls for the same symbol share a single fetch.
// Returns a map of timeframe -> number of new bars inserted.
func (s *Service) EnsureData(ctx context.Context, symbol string, timeframes []string, start, end time.Time) (map[string]int, error) {
	// Request coalescing: if someone is already fetching this symbol, wait for them.
	req := &pendingRequest{done: make(chan struct{})}
	if existing, loaded := s.pending.LoadOrStore(symbol, req); loaded {
		// Another goroutine is already working on this symbol.
		pending := existing.(*pendingRequest)
		s.logger.Debug("Coalescing request, waiting for existing fetch",
			"symbol", symbol,
		)
		select {
		case <-pending.done:
			return pending.result, pending.err
		case <-ctx.Done():
			return nil, ctx.Err()
		}
	}

	// We won the race — do the actual work.
	defer func() {
		close(req.done)
		s.pending.Delete(symbol)
	}()

	result, err := s.doEnsureData(ctx, symbol, timeframes, start, end)
	req.result = result
	req.err = err
	return result, err
}

// doEnsureData is the actual implementation of EnsureData without coalescing.
func (s *Service) doEnsureData(ctx context.Context, symbol string, timeframes []string, start, end time.Time) (map[string]int, error) {
	tickerID, err := s.db.GetOrCreateTicker(ctx, symbol)
	if err != nil {
		return nil, fmt.Errorf("get/create ticker %q: %w", symbol, err)
	}

	result := make(map[string]int)

	// Determine what needs to be fetched.
	needs1Min := false
	needs1Day := false
	var needsAgg []string

	for _, tf := range timeframes {
		switch tf {
		case "1Min":
			needs1Min = true
		case "1Day":
			needs1Day = true
		case "5Min", "15Min", "1Hour":
			needs1Min = true // Aggregation requires 1Min.
			needsAgg = append(needsAgg, tf)
		default:
			s.logger.Warn("Ignoring unsupported timeframe", "timeframe", tf, "symbol", symbol)
		}
	}

	// Step 1: Ensure 1Min bars (prerequisite for aggregation).
	if needs1Min {
		n, err := s.ensure1Min(ctx, tickerID, symbol, start, end)
		if err != nil {
			s.handleFetchError(ctx, symbol, err)
			return result, fmt.Errorf("ensure 1Min for %s: %w", symbol, err)
		}
		result["1Min"] = n
	}

	// Step 2: Aggregate 1Min -> higher timeframes.
	for _, tf := range needsAgg {
		n, err := s.aggregateTimeframe(ctx, tickerID, symbol, tf, start, end)
		if err != nil {
			s.logger.Error("Aggregation failed",
				"symbol", symbol, "timeframe", tf, "error", err,
			)
			// Continue with other timeframes — partial success is better than nothing.
			continue
		}
		result[tf] = n
	}

	// Step 3: Ensure 1Day (fetched directly, not aggregated).
	if needs1Day {
		n, err := s.ensure1Day(ctx, tickerID, symbol, start, end)
		if err != nil {
			s.handleFetchError(ctx, symbol, err)
			return result, fmt.Errorf("ensure 1Day for %s: %w", symbol, err)
		}
		result["1Day"] = n
	}

	s.logger.Info("EnsureData complete",
		"symbol", symbol,
		"result", result,
	)
	return result, nil
}

// handleFetchError checks if an Alpaca fetch error is a client error (4xx)
// and deactivates the ticker to prevent future polling for invalid symbols.
func (s *Service) handleFetchError(ctx context.Context, symbol string, err error) {
	if !alpaca.IsAlpacaAPIError(err) {
		return
	}
	s.logger.Warn("Deactivating ticker due to Alpaca API error",
		"symbol", symbol,
		"error", err,
	)
	if deactivateErr := s.db.DeactivateTicker(ctx, symbol); deactivateErr != nil {
		s.logger.Error("Failed to deactivate ticker",
			"symbol", symbol,
			"error", deactivateErr,
		)
	}
}

// ensure1Min fetches missing 1Min bars from Alpaca.
func (s *Service) ensure1Min(ctx context.Context, tickerID int, symbol string, start, end time.Time) (int, error) {
	return s.ensureFromAlpaca(ctx, tickerID, symbol, "1Min", start, end, time.Minute)
}

// ensure1Day fetches missing daily bars from Alpaca.
func (s *Service) ensure1Day(ctx context.Context, tickerID int, symbol string, start, end time.Time) (int, error) {
	return s.ensureFromAlpaca(ctx, tickerID, symbol, "1Day", start, end, 24*time.Hour)
}

// ensureFromAlpaca checks for gaps and fetches missing data from Alpaca.
func (s *Service) ensureFromAlpaca(ctx context.Context, tickerID int, symbol, timeframe string, start, end time.Time, buffer time.Duration) (int, error) {
	latest, err := s.db.GetLatestTimestamp(ctx, tickerID, timeframe)
	if err != nil {
		return 0, fmt.Errorf("getting latest timestamp: %w", err)
	}

	fetchStart := start
	if latest != nil {
		// Data exists — check if we're up to date.
		if end.Before(latest.Add(buffer)) || end.Equal(latest.Add(buffer)) {
			s.logger.Debug("Data up to date, skipping fetch",
				"symbol", symbol,
				"timeframe", timeframe,
				"latest_in_db", latest,
				"requested_end", end,
			)
			return 0, nil
		}
		fetchStart = latest.Add(buffer)
	}

	s.logger.Info("Fetching from Alpaca",
		"symbol", symbol,
		"timeframe", timeframe,
		"start", fetchStart.Format(time.RFC3339),
		"end", end.Format(time.RFC3339),
	)

	bars, err := s.alpaca.FetchBars(ctx, symbol, timeframe, fetchStart, end)
	if err != nil {
		return 0, fmt.Errorf("fetching bars: %w", err)
	}

	if len(bars) == 0 {
		s.logger.Debug("No new bars from Alpaca",
			"symbol", symbol, "timeframe", timeframe,
		)
		return 0, nil
	}

	inserted, err := s.db.BulkInsertBars(ctx, tickerID, timeframe, "alpaca", bars)
	if err != nil {
		return 0, fmt.Errorf("inserting bars: %w", err)
	}

	// Update sync log.
	lastTS := bars[len(bars)-1].Timestamp
	firstTS := bars[0].Timestamp
	if err := s.db.UpdateSyncLog(ctx, db.SyncLogEntry{
		TickerID:            tickerID,
		Timeframe:           timeframe,
		LastSyncedTimestamp:  &lastTS,
		FirstSyncedTimestamp: &firstTS,
		BarsFetched:         inserted,
		Status:              "success",
	}); err != nil {
		s.logger.Warn("Failed to update sync log",
			"symbol", symbol, "timeframe", timeframe, "error", err,
		)
	}

	s.logger.Info("Bars inserted",
		"symbol", symbol,
		"timeframe", timeframe,
		"fetched", len(bars),
		"inserted", inserted,
	)
	return inserted, nil
}

// aggregateTimeframe reads 1Min bars and aggregates them to the target timeframe.
func (s *Service) aggregateTimeframe(ctx context.Context, tickerID int, symbol, targetTF string, start, end time.Time) (int, error) {
	// Find where we left off for the target timeframe.
	latest, err := s.db.GetLatestTimestamp(ctx, tickerID, targetTF)
	if err != nil {
		return 0, fmt.Errorf("getting latest %s timestamp: %w", targetTF, err)
	}

	after := start
	if latest != nil {
		after = *latest
	}

	// Read 1Min bars after that point.
	bars1Min, err := s.db.GetBars1Min(ctx, tickerID, after)
	if err != nil {
		return 0, fmt.Errorf("reading 1Min bars: %w", err)
	}

	if len(bars1Min) == 0 {
		s.logger.Debug("No 1Min bars to aggregate",
			"symbol", symbol, "target", targetTF, "after", after,
		)
		return 0, nil
	}

	// Aggregate.
	aggBars, err := aggregator.Aggregate(bars1Min, targetTF)
	if err != nil {
		return 0, fmt.Errorf("aggregating to %s: %w", targetTF, err)
	}

	if len(aggBars) == 0 {
		return 0, nil
	}

	// Insert aggregated bars.
	inserted, err := s.db.BulkInsertBars(ctx, tickerID, targetTF, "aggregated", aggBars)
	if err != nil {
		return 0, fmt.Errorf("inserting aggregated bars: %w", err)
	}

	// Update sync log.
	lastTS := aggBars[len(aggBars)-1].Timestamp
	firstTS := aggBars[0].Timestamp
	if err := s.db.UpdateSyncLog(ctx, db.SyncLogEntry{
		TickerID:            tickerID,
		Timeframe:           targetTF,
		LastSyncedTimestamp:  &lastTS,
		FirstSyncedTimestamp: &firstTS,
		BarsFetched:         inserted,
		Status:              "success",
	}); err != nil {
		s.logger.Warn("Failed to update sync log",
			"symbol", symbol, "timeframe", targetTF, "error", err,
		)
	}

	s.logger.Info("Aggregation complete",
		"symbol", symbol,
		"target", targetTF,
		"source_bars", len(bars1Min),
		"aggregated", len(aggBars),
		"inserted", inserted,
	)
	return inserted, nil
}
