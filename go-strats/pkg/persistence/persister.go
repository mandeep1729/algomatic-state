package persistence

import (
	"context"
	"io"

	"github.com/algomatic/strats100/go-strats/pkg/types"
)

// Persister defines the interface for strategy result persistence.
// Implemented by both Client (direct pgx) and GRPCClient (data-service gRPC).
type Persister interface {
	// LookupStrategyID returns the database ID for a strategy by name.
	// Returns 0 if the strategy is not found.
	LookupStrategyID(ctx context.Context, name string) (int, error)

	// SaveResults inserts aggregated results.
	// Returns a map of GroupKey -> result_id for FK linking, and the inserted count.
	SaveResults(ctx context.Context, results []AggregatedResult) (map[GroupKey]int64, int, error)

	// SaveTrades bulk-inserts trade records.
	SaveTrades(ctx context.Context, trades []TradeRecord) (int, error)

	// Persist saves both aggregated results and individual trades.
	// Returns (resultCount, tradeCount, error).
	Persist(
		ctx context.Context,
		trades []TradeRecord,
		engineTrades []types.Trade,
		results []AggregatedResult,
		persistTrades bool,
	) (int, int, error)

	// Close releases resources.
	io.Closer
}
