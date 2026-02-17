package repository

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// ProbeStrategyRepo handles reads from the probe_strategies table.
type ProbeStrategyRepo struct {
	pool   *pgxpool.Pool
	logger *slog.Logger
}

// NewProbeStrategyRepo creates a new ProbeStrategyRepo.
func NewProbeStrategyRepo(pool *pgxpool.Pool, logger *slog.Logger) *ProbeStrategyRepo {
	return &ProbeStrategyRepo{pool: pool, logger: logger}
}

// LookupByName returns the database ID for a strategy by name.
// Returns 0, false if the strategy is not found.
func (r *ProbeStrategyRepo) LookupByName(ctx context.Context, name string) (int32, bool, error) {
	var id int32
	err := r.pool.QueryRow(ctx,
		"SELECT id FROM probe_strategies WHERE name = $1 AND is_active = true",
		name,
	).Scan(&id)
	if err != nil {
		if err == pgx.ErrNoRows {
			r.logger.Debug("Strategy not found", "name", name)
			return 0, false, nil
		}
		return 0, false, fmt.Errorf("looking up strategy %q: %w", name, err)
	}
	r.logger.Debug("Strategy found", "name", name, "id", id)
	return id, true, nil
}
