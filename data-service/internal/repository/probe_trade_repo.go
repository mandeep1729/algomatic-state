package repository

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// ProbeTrade holds the fields for a strategy_probe_trades row.
type ProbeTrade struct {
	ResultID           int64
	Ticker             string
	OpenTimestamp      time.Time
	CloseTimestamp     time.Time
	Direction          string
	OpenJustification  string
	CloseJustification string
	PnL                float64
	PnLPct             float64
	BarsHeld           int32
	MaxDrawdown        float64
	MaxProfit          float64
	PnLStd             float64
}

// ProbeTradeRepo handles writes to the strategy_probe_trades table.
type ProbeTradeRepo struct {
	pool   *pgxpool.Pool
	logger *slog.Logger
}

// NewProbeTradeRepo creates a new ProbeTradeRepo.
func NewProbeTradeRepo(pool *pgxpool.Pool, logger *slog.Logger) *ProbeTradeRepo {
	return &ProbeTradeRepo{pool: pool, logger: logger}
}

// SaveTrades bulk-inserts trade records using pgx CopyFrom.
// Each trade must have its ResultID set to the FK pointing at strategy_probe_results.
func (r *ProbeTradeRepo) SaveTrades(ctx context.Context, trades []ProbeTrade) (int, error) {
	if len(trades) == 0 {
		return 0, nil
	}

	tx, err := r.pool.Begin(ctx)
	if err != nil {
		return 0, fmt.Errorf("beginning transaction: %w", err)
	}
	defer tx.Rollback(ctx) //nolint:errcheck

	rows := make([][]interface{}, len(trades))
	for i, t := range trades {
		rows[i] = []interface{}{
			t.ResultID,
			t.Ticker,
			t.OpenTimestamp,
			t.CloseTimestamp,
			t.Direction,
			t.OpenJustification,
			t.CloseJustification,
			t.PnL,
			t.PnLPct,
			t.BarsHeld,
			t.MaxDrawdown,
			t.MaxProfit,
			t.PnLStd,
		}
	}

	copyCount, err := tx.CopyFrom(
		ctx,
		pgx.Identifier{"strategy_probe_trades"},
		[]string{
			"strategy_probe_result_id",
			"ticker", "open_timestamp", "close_timestamp",
			"direction", "open_justification", "close_justification",
			"pnl", "pnl_pct", "bars_held",
			"max_drawdown", "max_profit", "pnl_std",
		},
		pgx.CopyFromRows(rows),
	)
	if err != nil {
		return 0, fmt.Errorf("bulk inserting trades: %w", err)
	}

	if err := tx.Commit(ctx); err != nil {
		return 0, fmt.Errorf("committing trades transaction: %w", err)
	}

	r.logger.Info("Saved trade records", "count", copyCount)
	return int(copyCount), nil
}
