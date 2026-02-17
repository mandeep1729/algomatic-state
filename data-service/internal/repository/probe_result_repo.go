package repository

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// ProbeResult holds the fields for a strategy_probe_results row.
type ProbeResult struct {
	RunID       string
	Symbol      string
	StrategyID  int32
	PeriodStart time.Time
	PeriodEnd   time.Time
	Timeframe   string
	RiskProfile string
	OpenDay     time.Time // Date only (YYYY-MM-DD)
	OpenHour    int32
	LongShort   string
	NumTrades   int32
	PnLMean     float64
	PnLStd      float64
	MaxDrawdown float64
	MaxProfit   float64
}

// ResultGroupKey identifies a unique aggregation group for FK mapping.
type ResultGroupKey struct {
	OpenDay   string // YYYY-MM-DD
	OpenHour  int32
	LongShort string
}

// ResultIDMapping maps a group key to its database-assigned result ID.
type ResultIDMapping struct {
	Key      ResultGroupKey
	ResultID int64
}

// ProbeResultRepo handles writes to the strategy_probe_results table.
type ProbeResultRepo struct {
	pool   *pgxpool.Pool
	logger *slog.Logger
}

// NewProbeResultRepo creates a new ProbeResultRepo.
func NewProbeResultRepo(pool *pgxpool.Pool, logger *slog.Logger) *ProbeResultRepo {
	return &ProbeResultRepo{pool: pool, logger: logger}
}

// SaveResults inserts aggregated results with ON CONFLICT DO NOTHING.
// Returns mappings from group keys to result IDs, and the count of rows inserted.
func (r *ProbeResultRepo) SaveResults(ctx context.Context, results []ProbeResult) ([]ResultIDMapping, int, error) {
	if len(results) == 0 {
		return nil, 0, nil
	}

	tx, err := r.pool.Begin(ctx)
	if err != nil {
		return nil, 0, fmt.Errorf("beginning transaction: %w", err)
	}
	defer tx.Rollback(ctx) //nolint:errcheck

	mappings := make([]ResultIDMapping, 0, len(results))
	inserted := 0

	for _, res := range results {
		var id int64
		err := tx.QueryRow(ctx,
			`INSERT INTO strategy_probe_results
				(run_id, symbol, strategy_id, period_start, period_end,
				 timeframe, risk_profile, open_day, open_hour, long_short,
				 num_trades, pnl_mean, pnl_std, max_drawdown, max_profit)
			 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
			 ON CONFLICT ON CONSTRAINT uq_probe_result_dimensions DO NOTHING
			 RETURNING id`,
			res.RunID, res.Symbol, res.StrategyID, res.PeriodStart, res.PeriodEnd,
			res.Timeframe, res.RiskProfile, res.OpenDay, res.OpenHour, res.LongShort,
			res.NumTrades, res.PnLMean, res.PnLStd, res.MaxDrawdown, res.MaxProfit,
		).Scan(&id)

		key := ResultGroupKey{
			OpenDay:   res.OpenDay.Format("2006-01-02"),
			OpenHour:  res.OpenHour,
			LongShort: res.LongShort,
		}

		if err != nil {
			if err == pgx.ErrNoRows {
				// ON CONFLICT DO NOTHING — look up existing ID
				existingID, lookupErr := r.lookupResultID(ctx, tx, res)
				if lookupErr != nil {
					r.logger.Warn("Could not look up existing result row",
						"error", lookupErr,
						"run_id", res.RunID,
						"open_day", res.OpenDay,
					)
					continue
				}
				mappings = append(mappings, ResultIDMapping{Key: key, ResultID: existingID})
				continue
			}
			return nil, 0, fmt.Errorf("inserting result: %w", err)
		}

		mappings = append(mappings, ResultIDMapping{Key: key, ResultID: id})
		inserted++
	}

	if err := tx.Commit(ctx); err != nil {
		return nil, 0, fmt.Errorf("committing results transaction: %w", err)
	}

	r.logger.Info("Saved aggregated results", "inserted", inserted, "total", len(results))
	return mappings, inserted, nil
}

// lookupResultID queries the existing result ID when ON CONFLICT fires.
func (r *ProbeResultRepo) lookupResultID(ctx context.Context, tx pgx.Tx, res ProbeResult) (int64, error) {
	var id int64
	err := tx.QueryRow(ctx,
		`SELECT id FROM strategy_probe_results
		 WHERE run_id = $1 AND symbol = $2 AND strategy_id = $3
		   AND timeframe = $4 AND risk_profile = $5
		   AND open_day = $6 AND open_hour = $7 AND long_short = $8`,
		res.RunID, res.Symbol, res.StrategyID,
		res.Timeframe, res.RiskProfile,
		res.OpenDay, res.OpenHour, res.LongShort,
	).Scan(&id)
	return id, err
}
