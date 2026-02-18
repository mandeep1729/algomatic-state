package repository

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"

	"github.com/jackc/pgx/v5/pgxpool"
)

// ActivityRepo provides database access for agent activity logs.
type ActivityRepo struct {
	pool   *pgxpool.Pool
	logger *slog.Logger
}

// NewActivityRepo creates a new ActivityRepo.
func NewActivityRepo(pool *pgxpool.Pool, logger *slog.Logger) *ActivityRepo {
	return &ActivityRepo{pool: pool, logger: logger}
}

// Log inserts a new activity log entry.
func (r *ActivityRepo) Log(
	ctx context.Context,
	agentID int,
	accountID int,
	activityType string,
	message string,
	details json.RawMessage,
	severity string,
) error {
	_, err := r.pool.Exec(ctx, `
		INSERT INTO agent_activity_log (agent_id, account_id, activity_type, message, details, severity)
		VALUES ($1, $2, $3, $4, $5, $6)
	`, agentID, accountID, activityType, message, details, severity)
	if err != nil {
		return fmt.Errorf("logging activity for agent %d: %w", agentID, err)
	}

	r.logger.Debug("Logged activity",
		"agent_id", agentID, "type", activityType, "severity", severity,
	)
	return nil
}
