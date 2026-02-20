package repository

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Ticker represents a row from the tickers table.
type Ticker struct {
	ID        int32
	Symbol    string
	Name      string
	Exchange  string
	AssetType string
	IsActive  bool
	CreatedAt time.Time
	UpdatedAt time.Time
}

// TickerRepo handles ticker table operations.
type TickerRepo struct {
	pool   *pgxpool.Pool
	logger *slog.Logger
}

// NewTickerRepo creates a new TickerRepo.
func NewTickerRepo(pool *pgxpool.Pool, logger *slog.Logger) *TickerRepo {
	return &TickerRepo{pool: pool, logger: logger}
}

// GetTicker returns a ticker by symbol.
func (r *TickerRepo) GetTicker(ctx context.Context, symbol string) (*Ticker, error) {
	var t Ticker
	err := r.pool.QueryRow(ctx,
		`SELECT id, symbol, COALESCE(name, ''), COALESCE(exchange, ''), COALESCE(asset_type, 'stock'), is_active, created_at, updated_at
		 FROM tickers WHERE symbol = $1`, symbol,
	).Scan(&t.ID, &t.Symbol, &t.Name, &t.Exchange, &t.AssetType, &t.IsActive, &t.CreatedAt, &t.UpdatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("querying ticker %q: %w", symbol, err)
	}
	return &t, nil
}

// ListTickers returns tickers, optionally filtered by active status.
func (r *TickerRepo) ListTickers(ctx context.Context, activeOnly bool) ([]Ticker, error) {
	query := `SELECT id, symbol, COALESCE(name, ''), COALESCE(exchange, ''), COALESCE(asset_type, 'stock'), is_active, created_at, updated_at FROM tickers`
	if activeOnly {
		query += ` WHERE is_active = true`
	}
	query += ` ORDER BY symbol`

	rows, err := r.pool.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("querying tickers: %w", err)
	}
	defer rows.Close()

	var tickers []Ticker
	for rows.Next() {
		var t Ticker
		if err := rows.Scan(&t.ID, &t.Symbol, &t.Name, &t.Exchange, &t.AssetType, &t.IsActive, &t.CreatedAt, &t.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scanning ticker row: %w", err)
		}
		tickers = append(tickers, t)
	}
	return tickers, rows.Err()
}

// GetOrCreateTicker returns the ticker for the given symbol, creating it if needed.
func (r *TickerRepo) GetOrCreateTicker(ctx context.Context, symbol, name, exchange, assetType string) (*Ticker, bool, error) {
	if assetType == "" {
		assetType = "stock"
	}

	// Insert or re-activate on conflict (ensures previously deactivated tickers
	// become active again when explicitly requested).
	tag, err := r.pool.Exec(ctx,
		`INSERT INTO tickers (symbol, name, exchange, asset_type, is_active, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, true, NOW(), NOW())
		 ON CONFLICT (symbol) DO UPDATE SET is_active = true, updated_at = NOW()`,
		symbol, nilIfEmpty(name), nilIfEmpty(exchange), assetType,
	)
	if err != nil {
		return nil, false, fmt.Errorf("inserting ticker %q: %w", symbol, err)
	}
	created := tag.RowsAffected() > 0

	t, err := r.GetTicker(ctx, symbol)
	if err != nil {
		return nil, false, err
	}
	if t == nil {
		return nil, false, fmt.Errorf("ticker %q not found after insert", symbol)
	}

	r.logger.Debug("GetOrCreateTicker",
		"symbol", symbol,
		"created", created,
		"ticker_id", t.ID,
	)
	return t, created, nil
}

// BulkUpsertTickers inserts or updates multiple tickers.
func (r *TickerRepo) BulkUpsertTickers(ctx context.Context, tickers []Ticker) (int, error) {
	if len(tickers) == 0 {
		return 0, nil
	}

	batch := &pgx.Batch{}
	for _, t := range tickers {
		assetType := t.AssetType
		if assetType == "" {
			assetType = "stock"
		}
		batch.Queue(
			`INSERT INTO tickers (symbol, name, exchange, asset_type, is_active, created_at, updated_at)
			 VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
			 ON CONFLICT (symbol) DO UPDATE SET
			   name = COALESCE(EXCLUDED.name, tickers.name),
			   exchange = COALESCE(EXCLUDED.exchange, tickers.exchange),
			   asset_type = EXCLUDED.asset_type,
			   is_active = EXCLUDED.is_active,
			   updated_at = NOW()`,
			t.Symbol, nilIfEmpty(t.Name), nilIfEmpty(t.Exchange), assetType, t.IsActive,
		)
	}

	results := r.pool.SendBatch(ctx, batch)
	upserted := 0
	for range tickers {
		tag, err := results.Exec()
		if err != nil {
			results.Close()
			return upserted, fmt.Errorf("upserting ticker: %w", err)
		}
		upserted += int(tag.RowsAffected())
	}
	if err := results.Close(); err != nil {
		return upserted, fmt.Errorf("closing batch: %w", err)
	}

	r.logger.Debug("BulkUpsertTickers", "count", upserted)
	return upserted, nil
}

func nilIfEmpty(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}
