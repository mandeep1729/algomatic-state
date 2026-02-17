package repository

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// DataSyncLog represents a row from the data_sync_log table.
type DataSyncLog struct {
	ID                   int32
	TickerID             int32
	Timeframe            string
	LastSyncedTimestamp   *time.Time
	FirstSyncedTimestamp *time.Time
	LastSyncAt           time.Time
	BarsFetched          int32
	TotalBars            int32
	Status               string
	ErrorMessage         *string
}

// SyncLogRepo handles data_sync_log table operations.
type SyncLogRepo struct {
	pool   *pgxpool.Pool
	logger *slog.Logger
}

// NewSyncLogRepo creates a new SyncLogRepo.
func NewSyncLogRepo(pool *pgxpool.Pool, logger *slog.Logger) *SyncLogRepo {
	return &SyncLogRepo{pool: pool, logger: logger}
}

const syncLogColumns = `id, ticker_id, timeframe, last_synced_timestamp, first_synced_timestamp, last_sync_at, bars_fetched, total_bars, status, error_message`

func scanSyncLog(row pgx.Row) (*DataSyncLog, error) {
	var s DataSyncLog
	err := row.Scan(&s.ID, &s.TickerID, &s.Timeframe, &s.LastSyncedTimestamp,
		&s.FirstSyncedTimestamp, &s.LastSyncAt, &s.BarsFetched, &s.TotalBars,
		&s.Status, &s.ErrorMessage)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, err
	}
	return &s, nil
}

// GetSyncLog returns the sync log entry for a ticker/timeframe.
func (r *SyncLogRepo) GetSyncLog(ctx context.Context, tickerID int32, timeframe string) (*DataSyncLog, error) {
	s, err := scanSyncLog(r.pool.QueryRow(ctx,
		fmt.Sprintf(`SELECT %s FROM data_sync_log WHERE ticker_id = $1 AND timeframe = $2`, syncLogColumns),
		tickerID, timeframe,
	))
	if err != nil {
		return nil, fmt.Errorf("querying sync log: %w", err)
	}
	return s, nil
}

// UpdateSyncLog upserts a data_sync_log entry.
// total_bars is incremented by bars_fetched on conflict (matching existing Go marketdata-service pattern).
func (r *SyncLogRepo) UpdateSyncLog(ctx context.Context, tickerID int32, timeframe string, lastSyncedTS, firstSyncedTS *time.Time, barsFetched int32, status string, errorMessage *string) (*DataSyncLog, error) {
	s, err := scanSyncLog(r.pool.QueryRow(ctx,
		fmt.Sprintf(`INSERT INTO data_sync_log (ticker_id, timeframe, last_synced_timestamp, first_synced_timestamp, last_sync_at, bars_fetched, total_bars, status, error_message)
		 VALUES ($1, $2, $3, $4, NOW(), $5, $5, $6, $7)
		 ON CONFLICT (ticker_id, timeframe) DO UPDATE SET
		   last_synced_timestamp = COALESCE(EXCLUDED.last_synced_timestamp, data_sync_log.last_synced_timestamp),
		   first_synced_timestamp = COALESCE(EXCLUDED.first_synced_timestamp, data_sync_log.first_synced_timestamp),
		   last_sync_at = NOW(),
		   bars_fetched = EXCLUDED.bars_fetched,
		   total_bars = data_sync_log.total_bars + EXCLUDED.bars_fetched,
		   status = EXCLUDED.status,
		   error_message = EXCLUDED.error_message
		 RETURNING %s`, syncLogColumns),
		tickerID, timeframe, lastSyncedTS, firstSyncedTS, barsFetched, status, errorMessage,
	))
	if err != nil {
		return nil, fmt.Errorf("upserting sync log: %w", err)
	}

	r.logger.Debug("UpdateSyncLog",
		"ticker_id", tickerID,
		"timeframe", timeframe,
		"bars_fetched", barsFetched,
		"status", status,
	)
	return s, nil
}

// ListSyncLogs returns all sync log entries, optionally filtered by ticker symbol.
func (r *SyncLogRepo) ListSyncLogs(ctx context.Context, symbol *string) ([]DataSyncLog, error) {
	var query string
	var args []any

	if symbol != nil && *symbol != "" {
		query = fmt.Sprintf(`SELECT dsl.%s FROM data_sync_log dsl
			JOIN tickers t ON t.id = dsl.ticker_id
			WHERE t.symbol = $1
			ORDER BY dsl.ticker_id, dsl.timeframe`,
			"id, ticker_id, timeframe, last_synced_timestamp, first_synced_timestamp, last_sync_at, bars_fetched, total_bars, status, error_message")
		args = []any{*symbol}
	} else {
		query = fmt.Sprintf(`SELECT %s FROM data_sync_log ORDER BY ticker_id, timeframe`, syncLogColumns)
	}

	rows, err := r.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("querying sync logs: %w", err)
	}
	defer rows.Close()

	var logs []DataSyncLog
	for rows.Next() {
		var s DataSyncLog
		if err := rows.Scan(&s.ID, &s.TickerID, &s.Timeframe, &s.LastSyncedTimestamp,
			&s.FirstSyncedTimestamp, &s.LastSyncAt, &s.BarsFetched, &s.TotalBars,
			&s.Status, &s.ErrorMessage); err != nil {
			return nil, fmt.Errorf("scanning sync log row: %w", err)
		}
		logs = append(logs, s)
	}
	return logs, rows.Err()
}
