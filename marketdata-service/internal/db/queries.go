package db

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
)

// OHLCVBar represents a single OHLCV bar row.
type OHLCVBar struct {
	Timestamp  time.Time
	Open       float64
	High       float64
	Low        float64
	Close      float64
	Volume     int64
	TradeCount *int
	Source     string
}

// SyncLogEntry holds data for a data_sync_log upsert.
type SyncLogEntry struct {
	TickerID            int
	Timeframe           string
	LastSyncedTimestamp  *time.Time
	FirstSyncedTimestamp *time.Time
	BarsFetched         int
	TotalBars           int
	Status              string
	ErrorMessage        *string
}

// GetOrCreateTicker returns the ticker ID for the given symbol, creating it if needed.
func (c *Client) GetOrCreateTicker(ctx context.Context, symbol string) (int, error) {
	// Try insert first (does nothing on conflict).
	_, err := c.pool.Exec(ctx,
		`INSERT INTO tickers (symbol, is_active, created_at, updated_at)
		 VALUES ($1, true, NOW(), NOW())
		 ON CONFLICT (symbol) DO NOTHING`,
		symbol,
	)
	if err != nil {
		return 0, fmt.Errorf("inserting ticker %q: %w", symbol, err)
	}

	// Select the id.
	var id int
	err = c.pool.QueryRow(ctx,
		`SELECT id FROM tickers WHERE symbol = $1`, symbol,
	).Scan(&id)
	if err != nil {
		return 0, fmt.Errorf("selecting ticker %q: %w", symbol, err)
	}

	return id, nil
}

// GetActiveTickers returns all active ticker symbols ordered alphabetically.
func (c *Client) GetActiveTickers(ctx context.Context) ([]string, error) {
	rows, err := c.pool.Query(ctx,
		`SELECT symbol FROM tickers WHERE is_active = true ORDER BY symbol`,
	)
	if err != nil {
		return nil, fmt.Errorf("querying active tickers: %w", err)
	}
	defer rows.Close()

	var symbols []string
	for rows.Next() {
		var s string
		if err := rows.Scan(&s); err != nil {
			return nil, fmt.Errorf("scanning ticker row: %w", err)
		}
		symbols = append(symbols, s)
	}
	return symbols, rows.Err()
}

// GetLatestTimestamp returns the most recent bar timestamp for a ticker/timeframe.
// Returns nil if no bars exist.
func (c *Client) GetLatestTimestamp(ctx context.Context, tickerID int, timeframe string) (*time.Time, error) {
	var ts *time.Time
	err := c.pool.QueryRow(ctx,
		`SELECT MAX(timestamp) FROM ohlcv_bars WHERE ticker_id = $1 AND timeframe = $2`,
		tickerID, timeframe,
	).Scan(&ts)
	if err != nil {
		return nil, fmt.Errorf("getting latest timestamp: %w", err)
	}
	return ts, nil
}

// GetBars1Min returns 1Min bars for a ticker after the given timestamp, ordered ascending.
func (c *Client) GetBars1Min(ctx context.Context, tickerID int, after time.Time) ([]OHLCVBar, error) {
	rows, err := c.pool.Query(ctx,
		`SELECT timestamp, open, high, low, close, volume
		 FROM ohlcv_bars
		 WHERE ticker_id = $1 AND timeframe = '1Min' AND timestamp > $2
		 ORDER BY timestamp ASC`,
		tickerID, after,
	)
	if err != nil {
		return nil, fmt.Errorf("querying 1Min bars: %w", err)
	}
	defer rows.Close()

	var bars []OHLCVBar
	for rows.Next() {
		var b OHLCVBar
		if err := rows.Scan(&b.Timestamp, &b.Open, &b.High, &b.Low, &b.Close, &b.Volume); err != nil {
			return nil, fmt.Errorf("scanning bar row: %w", err)
		}
		bars = append(bars, b)
	}
	return bars, rows.Err()
}

// BulkInsertBars inserts OHLCV bars in batches of 1000 using pgx.Batch.
// Returns the number of new rows inserted (conflicts are silently skipped).
func (c *Client) BulkInsertBars(ctx context.Context, tickerID int, timeframe, source string, bars []OHLCVBar) (int, error) {
	if len(bars) == 0 {
		return 0, nil
	}

	const batchSize = 1000
	totalInserted := 0

	for i := 0; i < len(bars); i += batchSize {
		end := i + batchSize
		if end > len(bars) {
			end = len(bars)
		}
		chunk := bars[i:end]

		batch := &pgx.Batch{}
		for _, bar := range chunk {
			batch.Queue(
				`INSERT INTO ohlcv_bars (ticker_id, timeframe, timestamp, open, high, low, close, volume, source, created_at)
				 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
				 ON CONFLICT (ticker_id, timeframe, timestamp) DO NOTHING`,
				tickerID, timeframe, bar.Timestamp,
				bar.Open, bar.High, bar.Low, bar.Close,
				bar.Volume, source,
			)
		}

		results := c.pool.SendBatch(ctx, batch)
		for range chunk {
			tag, err := results.Exec()
			if err != nil {
				results.Close()
				return totalInserted, fmt.Errorf("executing batch insert: %w", err)
			}
			totalInserted += int(tag.RowsAffected())
		}
		if err := results.Close(); err != nil {
			return totalInserted, fmt.Errorf("closing batch results: %w", err)
		}

		c.logger.Debug("Batch insert complete",
			"ticker_id", tickerID,
			"timeframe", timeframe,
			"chunk_size", len(chunk),
			"offset", i,
		)
	}

	return totalInserted, nil
}

// UpdateSyncLog upserts a data_sync_log entry for the given ticker/timeframe.
func (c *Client) UpdateSyncLog(ctx context.Context, entry SyncLogEntry) error {
	_, err := c.pool.Exec(ctx,
		`INSERT INTO data_sync_log (ticker_id, timeframe, last_synced_timestamp, first_synced_timestamp, last_sync_at, bars_fetched, total_bars, status, error_message)
		 VALUES ($1, $2, $3, $4, NOW(), $5, $6, $7, $8)
		 ON CONFLICT (ticker_id, timeframe) DO UPDATE SET
		   last_synced_timestamp = COALESCE(EXCLUDED.last_synced_timestamp, data_sync_log.last_synced_timestamp),
		   first_synced_timestamp = COALESCE(EXCLUDED.first_synced_timestamp, data_sync_log.first_synced_timestamp),
		   last_sync_at = NOW(),
		   bars_fetched = EXCLUDED.bars_fetched,
		   total_bars = data_sync_log.total_bars + EXCLUDED.bars_fetched,
		   status = EXCLUDED.status,
		   error_message = EXCLUDED.error_message`,
		entry.TickerID, entry.Timeframe,
		entry.LastSyncedTimestamp, entry.FirstSyncedTimestamp,
		entry.BarsFetched, entry.TotalBars,
		entry.Status, entry.ErrorMessage,
	)
	if err != nil {
		return fmt.Errorf("upserting sync log: %w", err)
	}
	return nil
}
