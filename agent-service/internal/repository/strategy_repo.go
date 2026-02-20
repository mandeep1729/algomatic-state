package repository

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"

	"github.com/jackc/pgx/v5/pgxpool"
)

// AgentStrategyRow represents a row from the agent_strategies table.
type AgentStrategyRow struct {
	ID               int
	Name             string
	DisplayName      string
	Category         string
	Direction        string
	ATRStopMult      *float64
	ATRTargetMult    *float64
	TrailingATRMult  *float64
	TimeStopBars     *int
	IsPredefined     bool
	SourceStrategyID *int

	// JSONB condition columns for custom strategies
	EntryLong  json.RawMessage
	EntryShort json.RawMessage
	ExitLong   json.RawMessage
	ExitShort  json.RawMessage

	// Version for cache invalidation
	Version int
}

// StrategyRepo provides database access for agent strategies.
type StrategyRepo struct {
	pool   *pgxpool.Pool
	logger *slog.Logger
}

// NewStrategyRepo creates a new StrategyRepo.
func NewStrategyRepo(pool *pgxpool.Pool, logger *slog.Logger) *StrategyRepo {
	return &StrategyRepo{pool: pool, logger: logger}
}

// GetStrategy returns a strategy by ID.
func (r *StrategyRepo) GetStrategy(ctx context.Context, id int) (*AgentStrategyRow, error) {
	var s AgentStrategyRow
	err := r.pool.QueryRow(ctx, `
		SELECT id, name, display_name, category, direction,
			atr_stop_mult, atr_target_mult, trailing_atr_mult, time_stop_bars,
			is_predefined, source_strategy_id,
			entry_long, entry_short, exit_long, exit_short,
			version
		FROM agent_strategies
		WHERE id = $1
	`, id).Scan(
		&s.ID, &s.Name, &s.DisplayName, &s.Category, &s.Direction,
		&s.ATRStopMult, &s.ATRTargetMult, &s.TrailingATRMult, &s.TimeStopBars,
		&s.IsPredefined, &s.SourceStrategyID,
		&s.EntryLong, &s.EntryShort, &s.ExitLong, &s.ExitShort,
		&s.Version,
	)
	if err != nil {
		return nil, fmt.Errorf("getting strategy %d: %w", id, err)
	}
	return &s, nil
}
