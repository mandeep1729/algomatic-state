package repository

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// OHLCVBar represents a row from the ohlcv_bars table.
type OHLCVBar struct {
	ID         int64
	TickerID   int32
	Timeframe  string
	Timestamp  time.Time
	Open       float64
	High       float64
	Low        float64
	Close      float64
	Volume     int64
	TradeCount *int32
	Source     string
	CreatedAt  time.Time
}

// ValidTimeframes are the only supported timeframe values.
var ValidTimeframes = map[string]bool{
	"1Min":  true,
	"15Min": true,
	"1Hour": true,
	"1Day":  true,
}

// BarRepo handles ohlcv_bars table operations.
type BarRepo struct {
	pool   *pgxpool.Pool
	logger *slog.Logger
}

// NewBarRepo creates a new BarRepo.
func NewBarRepo(pool *pgxpool.Pool, logger *slog.Logger) *BarRepo {
	return &BarRepo{pool: pool, logger: logger}
}

const barColumns = `id, ticker_id, timeframe, timestamp, open, high, low, close, volume, trade_count, COALESCE(source, 'alpaca'), created_at`

func scanBar(row pgx.Row) (OHLCVBar, error) {
	var b OHLCVBar
	err := row.Scan(&b.ID, &b.TickerID, &b.Timeframe, &b.Timestamp,
		&b.Open, &b.High, &b.Low, &b.Close, &b.Volume, &b.TradeCount, &b.Source, &b.CreatedAt)
	return b, err
}

func scanBars(rows pgx.Rows) ([]OHLCVBar, error) {
	var bars []OHLCVBar
	for rows.Next() {
		var b OHLCVBar
		if err := rows.Scan(&b.ID, &b.TickerID, &b.Timeframe, &b.Timestamp,
			&b.Open, &b.High, &b.Low, &b.Close, &b.Volume, &b.TradeCount, &b.Source, &b.CreatedAt); err != nil {
			return nil, fmt.Errorf("scanning bar row: %w", err)
		}
		bars = append(bars, b)
	}
	return bars, rows.Err()
}

// GetBars returns bars for a ticker/timeframe with optional time range and pagination.
// Returns bars ordered by timestamp ASC. pageToken is the last timestamp from previous page.
func (r *BarRepo) GetBars(ctx context.Context, tickerID int32, timeframe string, start, end *time.Time, pageSize int32, pageToken *time.Time) ([]OHLCVBar, error) {
	if !ValidTimeframes[timeframe] {
		return nil, fmt.Errorf("invalid timeframe %q", timeframe)
	}
	if pageSize <= 0 {
		pageSize = 2000
	}

	query := fmt.Sprintf(`SELECT %s FROM ohlcv_bars WHERE ticker_id = $1 AND timeframe = $2`, barColumns)
	args := []any{tickerID, timeframe}
	argIdx := 3

	if start != nil {
		query += fmt.Sprintf(` AND timestamp >= $%d`, argIdx)
		args = append(args, *start)
		argIdx++
	}
	if end != nil {
		query += fmt.Sprintf(` AND timestamp <= $%d`, argIdx)
		args = append(args, *end)
		argIdx++
	}
	if pageToken != nil {
		query += fmt.Sprintf(` AND timestamp > $%d`, argIdx)
		args = append(args, *pageToken)
		argIdx++
	}

	query += fmt.Sprintf(` ORDER BY timestamp ASC LIMIT $%d`, argIdx)
	args = append(args, pageSize)

	rows, err := r.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("querying bars: %w", err)
	}
	defer rows.Close()

	return scanBars(rows)
}

// StreamBars returns all bars for a ticker/timeframe in order. Used for large reads.
func (r *BarRepo) StreamBars(ctx context.Context, tickerID int32, timeframe string, start, end *time.Time) ([]OHLCVBar, error) {
	if !ValidTimeframes[timeframe] {
		return nil, fmt.Errorf("invalid timeframe %q", timeframe)
	}

	query := fmt.Sprintf(`SELECT %s FROM ohlcv_bars WHERE ticker_id = $1 AND timeframe = $2`, barColumns)
	args := []any{tickerID, timeframe}
	argIdx := 3

	if start != nil {
		query += fmt.Sprintf(` AND timestamp >= $%d`, argIdx)
		args = append(args, *start)
		argIdx++
	}
	if end != nil {
		query += fmt.Sprintf(` AND timestamp <= $%d`, argIdx)
		args = append(args, *end)
	}
	query += ` ORDER BY timestamp ASC`

	rows, err := r.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("querying bars for stream: %w", err)
	}
	defer rows.Close()

	return scanBars(rows)
}

// BulkInsertBars inserts bars using pgx.Batch. Conflicts are silently skipped.
func (r *BarRepo) BulkInsertBars(ctx context.Context, tickerID int32, timeframe, source string, bars []OHLCVBar) (int, error) {
	if len(bars) == 0 {
		return 0, nil
	}
	if !ValidTimeframes[timeframe] {
		return 0, fmt.Errorf("invalid timeframe %q", timeframe)
	}
	if source == "" {
		source = "alpaca"
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
				`INSERT INTO ohlcv_bars (ticker_id, timeframe, timestamp, open, high, low, close, volume, trade_count, source, created_at)
				 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
				 ON CONFLICT (ticker_id, timeframe, timestamp) DO NOTHING`,
				tickerID, timeframe, bar.Timestamp,
				bar.Open, bar.High, bar.Low, bar.Close,
				bar.Volume, bar.TradeCount, source,
			)
		}

		results := r.pool.SendBatch(ctx, batch)
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

		r.logger.Debug("Batch insert complete",
			"ticker_id", tickerID,
			"timeframe", timeframe,
			"chunk_size", len(chunk),
			"offset", i,
		)
	}

	return totalInserted, nil
}

// DeleteBars deletes bars for a ticker/timeframe within an optional time range.
func (r *BarRepo) DeleteBars(ctx context.Context, tickerID int32, timeframe string, start, end *time.Time) (int, error) {
	if !ValidTimeframes[timeframe] {
		return 0, fmt.Errorf("invalid timeframe %q", timeframe)
	}

	query := `DELETE FROM ohlcv_bars WHERE ticker_id = $1 AND timeframe = $2`
	args := []any{tickerID, timeframe}
	argIdx := 3

	if start != nil {
		query += fmt.Sprintf(` AND timestamp >= $%d`, argIdx)
		args = append(args, *start)
		argIdx++
	}
	if end != nil {
		query += fmt.Sprintf(` AND timestamp <= $%d`, argIdx)
		args = append(args, *end)
	}

	tag, err := r.pool.Exec(ctx, query, args...)
	if err != nil {
		return 0, fmt.Errorf("deleting bars: %w", err)
	}
	return int(tag.RowsAffected()), nil
}

// GetLatestTimestamp returns the most recent bar timestamp for a ticker/timeframe.
func (r *BarRepo) GetLatestTimestamp(ctx context.Context, tickerID int32, timeframe string) (*time.Time, error) {
	if !ValidTimeframes[timeframe] {
		return nil, fmt.Errorf("invalid timeframe %q", timeframe)
	}

	var ts *time.Time
	err := r.pool.QueryRow(ctx,
		`SELECT MAX(timestamp) FROM ohlcv_bars WHERE ticker_id = $1 AND timeframe = $2`,
		tickerID, timeframe,
	).Scan(&ts)
	if err != nil {
		return nil, fmt.Errorf("getting latest timestamp: %w", err)
	}
	return ts, nil
}

// GetEarliestTimestamp returns the earliest bar timestamp for a ticker/timeframe.
func (r *BarRepo) GetEarliestTimestamp(ctx context.Context, tickerID int32, timeframe string) (*time.Time, error) {
	if !ValidTimeframes[timeframe] {
		return nil, fmt.Errorf("invalid timeframe %q", timeframe)
	}

	var ts *time.Time
	err := r.pool.QueryRow(ctx,
		`SELECT MIN(timestamp) FROM ohlcv_bars WHERE ticker_id = $1 AND timeframe = $2`,
		tickerID, timeframe,
	).Scan(&ts)
	if err != nil {
		return nil, fmt.Errorf("getting earliest timestamp: %w", err)
	}
	return ts, nil
}

// GetBarCount returns the number of bars for a ticker/timeframe within an optional time range.
func (r *BarRepo) GetBarCount(ctx context.Context, tickerID int32, timeframe string, start, end *time.Time) (int64, error) {
	if !ValidTimeframes[timeframe] {
		return 0, fmt.Errorf("invalid timeframe %q", timeframe)
	}

	query := `SELECT COUNT(*) FROM ohlcv_bars WHERE ticker_id = $1 AND timeframe = $2`
	args := []any{tickerID, timeframe}
	argIdx := 3

	if start != nil {
		query += fmt.Sprintf(` AND timestamp >= $%d`, argIdx)
		args = append(args, *start)
		argIdx++
	}
	if end != nil {
		query += fmt.Sprintf(` AND timestamp <= $%d`, argIdx)
		args = append(args, *end)
	}

	var count int64
	err := r.pool.QueryRow(ctx, query, args...).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("counting bars: %w", err)
	}
	return count, nil
}

// GetBarIdsForTimestamps returns a map of timestamp -> bar ID.
func (r *BarRepo) GetBarIdsForTimestamps(ctx context.Context, tickerID int32, timeframe string, timestamps []time.Time) (map[time.Time]int64, error) {
	if !ValidTimeframes[timeframe] {
		return nil, fmt.Errorf("invalid timeframe %q", timeframe)
	}
	if len(timestamps) == 0 {
		return map[time.Time]int64{}, nil
	}

	rows, err := r.pool.Query(ctx,
		`SELECT id, timestamp FROM ohlcv_bars
		 WHERE ticker_id = $1 AND timeframe = $2 AND timestamp = ANY($3)`,
		tickerID, timeframe, timestamps,
	)
	if err != nil {
		return nil, fmt.Errorf("querying bar IDs: %w", err)
	}
	defer rows.Close()

	result := make(map[time.Time]int64)
	for rows.Next() {
		var id int64
		var ts time.Time
		if err := rows.Scan(&id, &ts); err != nil {
			return nil, fmt.Errorf("scanning bar ID row: %w", err)
		}
		result[ts] = id
	}
	return result, rows.Err()
}
