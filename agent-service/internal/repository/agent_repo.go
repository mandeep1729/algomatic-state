package repository

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// TradingAgentRow represents a row from the trading_agents table.
type TradingAgentRow struct {
	ID                  int
	AccountID           int
	Name                string
	Symbol              string
	StrategyID          int
	Status              string
	Timeframe           string
	IntervalMinutes     int
	LookbackDays        int
	PositionSizeDollars float64
	RiskConfig          json.RawMessage
	ExitConfig          json.RawMessage
	Paper               bool
	LastRunAt           *time.Time
	LastSignal          *string
	ErrorMessage        *string
	ConsecutiveErrors   int
	CurrentPosition     json.RawMessage
	CreatedAt           time.Time
	UpdatedAt           time.Time
}

// AgentRepo provides database access for trading agents.
type AgentRepo struct {
	pool   *pgxpool.Pool
	logger *slog.Logger
}

// NewAgentRepo creates a new AgentRepo.
func NewAgentRepo(pool *pgxpool.Pool, logger *slog.Logger) *AgentRepo {
	return &AgentRepo{pool: pool, logger: logger}
}

// GetActiveAgents returns all agents with status='active'.
func (r *AgentRepo) GetActiveAgents(ctx context.Context) ([]TradingAgentRow, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, account_id, name, symbol, strategy_id, status,
			timeframe, interval_minutes, lookback_days, position_size_dollars,
			risk_config, exit_config, paper,
			last_run_at, last_signal, error_message, consecutive_errors,
			current_position, created_at, updated_at
		FROM trading_agents
		WHERE status = 'active'
	`)
	if err != nil {
		return nil, fmt.Errorf("querying active agents: %w", err)
	}
	defer rows.Close()

	var agents []TradingAgentRow
	for rows.Next() {
		var a TradingAgentRow
		if err := rows.Scan(
			&a.ID, &a.AccountID, &a.Name, &a.Symbol, &a.StrategyID, &a.Status,
			&a.Timeframe, &a.IntervalMinutes, &a.LookbackDays, &a.PositionSizeDollars,
			&a.RiskConfig, &a.ExitConfig, &a.Paper,
			&a.LastRunAt, &a.LastSignal, &a.ErrorMessage, &a.ConsecutiveErrors,
			&a.CurrentPosition, &a.CreatedAt, &a.UpdatedAt,
		); err != nil {
			return agents, fmt.Errorf("scanning agent row: %w", err)
		}
		agents = append(agents, a)
	}

	return agents, rows.Err()
}

// GetAgent returns a single agent by ID.
func (r *AgentRepo) GetAgent(ctx context.Context, id int) (*TradingAgentRow, error) {
	var a TradingAgentRow
	err := r.pool.QueryRow(ctx, `
		SELECT id, account_id, name, symbol, strategy_id, status,
			timeframe, interval_minutes, lookback_days, position_size_dollars,
			risk_config, exit_config, paper,
			last_run_at, last_signal, error_message, consecutive_errors,
			current_position, created_at, updated_at
		FROM trading_agents
		WHERE id = $1
	`, id).Scan(
		&a.ID, &a.AccountID, &a.Name, &a.Symbol, &a.StrategyID, &a.Status,
		&a.Timeframe, &a.IntervalMinutes, &a.LookbackDays, &a.PositionSizeDollars,
		&a.RiskConfig, &a.ExitConfig, &a.Paper,
		&a.LastRunAt, &a.LastSignal, &a.ErrorMessage, &a.ConsecutiveErrors,
		&a.CurrentPosition, &a.CreatedAt, &a.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("getting agent %d: %w", id, err)
	}
	return &a, nil
}

// UpdateLastRun updates the last run timestamp and signal, resetting error count.
func (r *AgentRepo) UpdateLastRun(ctx context.Context, id int, lastRunAt time.Time, lastSignal string) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE trading_agents
		SET last_run_at = $2, last_signal = $3, consecutive_errors = 0,
			error_message = NULL, updated_at = NOW()
		WHERE id = $1
	`, id, lastRunAt, lastSignal)
	if err != nil {
		return fmt.Errorf("updating last run for agent %d: %w", id, err)
	}
	return nil
}

// UpdateCurrentPosition updates the current_position JSONB.
func (r *AgentRepo) UpdateCurrentPosition(ctx context.Context, id int, positionJSON json.RawMessage) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE trading_agents
		SET current_position = $2, updated_at = NOW()
		WHERE id = $1
	`, id, positionJSON)
	if err != nil {
		return fmt.Errorf("updating position for agent %d: %w", id, err)
	}
	return nil
}

// IncrementErrors increments consecutive_errors and sets error_message.
// Returns the new consecutive_errors count.
func (r *AgentRepo) IncrementErrors(ctx context.Context, id int, errMsg string) (int, error) {
	var count int
	err := r.pool.QueryRow(ctx, `
		UPDATE trading_agents
		SET consecutive_errors = consecutive_errors + 1,
			error_message = $2, updated_at = NOW()
		WHERE id = $1
		RETURNING consecutive_errors
	`, id, errMsg).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("incrementing errors for agent %d: %w", id, err)
	}
	return count, nil
}

// SetStatus updates the agent's status.
func (r *AgentRepo) SetStatus(ctx context.Context, id int, status string) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE trading_agents
		SET status = $2, updated_at = NOW()
		WHERE id = $1
	`, id, status)
	if err != nil {
		return fmt.Errorf("setting status for agent %d: %w", id, err)
	}
	r.logger.Info("Set agent status", "agent_id", id, "status", status)
	return nil
}
