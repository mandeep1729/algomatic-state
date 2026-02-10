package persistence

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/algomatic/strats100/go-strats/pkg/types"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Client provides database persistence operations for strategy probe results.
type Client struct {
	pool   *pgxpool.Pool
	logger *slog.Logger
}

// NewClient creates a new database client with a connection pool.
func NewClient(ctx context.Context, connStr string, logger *slog.Logger) (*Client, error) {
	if logger == nil {
		logger = slog.Default()
	}

	config, err := pgxpool.ParseConfig(connStr)
	if err != nil {
		return nil, fmt.Errorf("parsing connection string: %w", err)
	}

	config.MaxConns = 10
	config.MinConns = 2
	config.MaxConnLifetime = 30 * time.Minute
	config.MaxConnIdleTime = 5 * time.Minute

	pool, err := pgxpool.NewWithConfig(ctx, config)
	if err != nil {
		return nil, fmt.Errorf("creating connection pool: %w", err)
	}

	// Verify connectivity
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("pinging database: %w", err)
	}

	logger.Info("Database connection pool established", "max_conns", config.MaxConns)
	return &Client{pool: pool, logger: logger}, nil
}

// Close shuts down the connection pool.
func (c *Client) Close() {
	c.pool.Close()
	c.logger.Info("Database connection pool closed")
}

// LookupStrategyID looks up the probe_strategies.id for a given strategy name.
// Returns 0 if the strategy is not found.
func (c *Client) LookupStrategyID(ctx context.Context, name string) (int, error) {
	var id int
	err := c.pool.QueryRow(ctx,
		"SELECT id FROM probe_strategies WHERE name = $1 AND is_active = true",
		name,
	).Scan(&id)
	if err != nil {
		if err == pgx.ErrNoRows {
			return 0, nil
		}
		return 0, fmt.Errorf("looking up strategy %q: %w", name, err)
	}
	return id, nil
}

// SaveResults inserts aggregated results into the strategy_probe_results table.
// Uses ON CONFLICT DO NOTHING to avoid duplicate errors on the unique constraint.
// Returns a map of GroupKey -> result_id for linking trades, and the count of rows inserted.
func (c *Client) SaveResults(ctx context.Context, results []AggregatedResult) (map[GroupKey]int64, int, error) {
	if len(results) == 0 {
		return nil, 0, nil
	}

	resultIDMap := make(map[GroupKey]int64, len(results))
	inserted := 0

	tx, err := c.pool.Begin(ctx)
	if err != nil {
		return nil, 0, fmt.Errorf("beginning transaction: %w", err)
	}
	defer tx.Rollback(ctx) //nolint:errcheck

	for _, r := range results {
		var id int64
		err := tx.QueryRow(ctx,
			`INSERT INTO strategy_probe_results
				(run_id, symbol, strategy_id, period_start, period_end,
				 timeframe, risk_profile, open_day, open_hour, long_short,
				 num_trades, pnl_mean, pnl_std, max_drawdown, max_profit)
			 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
			 ON CONFLICT ON CONSTRAINT uq_probe_result_dimensions DO NOTHING
			 RETURNING id`,
			r.RunID, r.Symbol, r.StrategyID, r.PeriodStart, r.PeriodEnd,
			r.Timeframe, r.RiskProfile, r.OpenDay, r.OpenHour, r.LongShort,
			r.NumTrades, r.PnLMean, r.PnLStd, r.MaxDrawdown, r.MaxProfit,
		).Scan(&id)

		if err != nil {
			if err == pgx.ErrNoRows {
				// ON CONFLICT DO NOTHING — row already exists, look up existing ID
				existingID, lookupErr := c.lookupResultID(ctx, tx, r)
				if lookupErr != nil {
					c.logger.Warn("Could not look up existing result row",
						"error", lookupErr,
						"run_id", r.RunID,
						"open_day", r.OpenDay,
						"open_hour", r.OpenHour,
						"long_short", r.LongShort,
					)
					continue
				}
				key := GroupKey{OpenDay: r.OpenDay, OpenHour: r.OpenHour, LongShort: r.LongShort}
				resultIDMap[key] = existingID
				continue
			}
			return nil, 0, fmt.Errorf("inserting result: %w", err)
		}

		key := GroupKey{OpenDay: r.OpenDay, OpenHour: r.OpenHour, LongShort: r.LongShort}
		resultIDMap[key] = id
		inserted++
	}

	if err := tx.Commit(ctx); err != nil {
		return nil, 0, fmt.Errorf("committing results transaction: %w", err)
	}

	c.logger.Info("Saved aggregated results",
		"inserted", inserted,
		"total", len(results),
	)
	return resultIDMap, inserted, nil
}

// lookupResultID queries the existing result ID when ON CONFLICT DO NOTHING fires.
func (c *Client) lookupResultID(ctx context.Context, tx pgx.Tx, r AggregatedResult) (int64, error) {
	var id int64
	err := tx.QueryRow(ctx,
		`SELECT id FROM strategy_probe_results
		 WHERE run_id = $1 AND symbol = $2 AND strategy_id = $3
		   AND timeframe = $4 AND risk_profile = $5
		   AND open_day = $6 AND open_hour = $7 AND long_short = $8`,
		r.RunID, r.Symbol, r.StrategyID,
		r.Timeframe, r.RiskProfile,
		r.OpenDay, r.OpenHour, r.LongShort,
	).Scan(&id)
	if err != nil {
		return 0, err
	}
	return id, nil
}

// SaveTrades inserts individual trade records into the strategy_probe_trades table.
// Each trade must have its ResultID set to the FK pointing at the corresponding
// strategy_probe_results row.
func (c *Client) SaveTrades(ctx context.Context, trades []TradeRecord) (int, error) {
	if len(trades) == 0 {
		return 0, nil
	}

	tx, err := c.pool.Begin(ctx)
	if err != nil {
		return 0, fmt.Errorf("beginning transaction: %w", err)
	}
	defer tx.Rollback(ctx) //nolint:errcheck

	// Use COPY for bulk insert performance
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

	c.logger.Info("Saved trade records", "count", copyCount)
	return int(copyCount), nil
}

// Persist saves both aggregated results and individual trades for a strategy run
// in a single workflow. This is the high-level entry point matching the Python
// runner's _store_results + _store_trades flow.
//
// Steps:
//  1. Aggregate trades into groups
//  2. Insert aggregated results (get back result IDs)
//  3. Build trade records, link to results via FK
//  4. Insert trade records
//
// Returns the number of result rows and trade rows inserted.
func (c *Client) Persist(
	ctx context.Context,
	trades []TradeRecord,
	engineTrades []types.Trade,
	results []AggregatedResult,
	persistTrades bool,
) (resultCount, tradeCount int, err error) {
	// Step 1: Save aggregated results
	resultIDMap, resultCount, err := c.SaveResults(ctx, results)
	if err != nil {
		return 0, 0, fmt.Errorf("saving results: %w", err)
	}

	if !persistTrades || len(trades) == 0 {
		return resultCount, 0, nil
	}

	// Step 2: Link trades to results
	matched, unmatched := MapTradesToResults(trades, engineTrades, resultIDMap)
	if unmatched > 0 {
		c.logger.Warn("Some trades could not be linked to result rows",
			"unmatched", unmatched,
			"total", len(trades),
		)
	}

	// Step 3: Save trades
	tradeCount, err = c.SaveTrades(ctx, matched)
	if err != nil {
		return resultCount, 0, fmt.Errorf("saving trades: %w", err)
	}

	return resultCount, tradeCount, nil
}
