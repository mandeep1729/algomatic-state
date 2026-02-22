package repository

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"math"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// ComputedFeature represents a row from the computed_features table.
type ComputedFeature struct {
	ID             int64
	BarID          *int64 // Nullable — aggregate timeframes have no real bar row
	TickerID       int32
	Timeframe      string
	Timestamp      time.Time
	Features       map[string]float64
	FeatureVersion string
	ModelID        *string
	StateID        *int32
	StateProb      *float64
	LogLikelihood  *float64
	CreatedAt      time.Time
}

// FeatureRepo handles computed_features table operations.
type FeatureRepo struct {
	pool   *pgxpool.Pool
	logger *slog.Logger
}

// NewFeatureRepo creates a new FeatureRepo.
func NewFeatureRepo(pool *pgxpool.Pool, logger *slog.Logger) *FeatureRepo {
	return &FeatureRepo{pool: pool, logger: logger}
}

// GetFeatures returns computed features for a ticker/timeframe with optional time range and pagination.
func (r *FeatureRepo) GetFeatures(ctx context.Context, tickerID int32, timeframe string, start, end *time.Time, pageSize int32, pageToken *time.Time) ([]ComputedFeature, error) {
	if !ValidTimeframes[timeframe] {
		return nil, fmt.Errorf("invalid timeframe %q", timeframe)
	}
	if pageSize <= 0 {
		pageSize = 2000
	}

	query := `SELECT id, bar_id, ticker_id, timeframe, timestamp, features, COALESCE(feature_version, ''), model_id, state_id, state_prob, log_likelihood, created_at
		 FROM computed_features WHERE ticker_id = $1 AND timeframe = $2`
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
		return nil, fmt.Errorf("querying features: %w", err)
	}
	defer rows.Close()

	return scanFeatures(rows)
}

func scanFeatures(rows pgx.Rows) ([]ComputedFeature, error) {
	var features []ComputedFeature
	for rows.Next() {
		var f ComputedFeature
		var featJSON []byte
		if err := rows.Scan(&f.ID, &f.BarID, &f.TickerID, &f.Timeframe, &f.Timestamp,
			&featJSON, &f.FeatureVersion, &f.ModelID, &f.StateID, &f.StateProb, &f.LogLikelihood, &f.CreatedAt); err != nil {
			return nil, fmt.Errorf("scanning feature row: %w", err)
		}
		if len(featJSON) > 0 {
			if err := json.Unmarshal(featJSON, &f.Features); err != nil {
				return nil, fmt.Errorf("unmarshaling features JSON: %w", err)
			}
		}
		features = append(features, f)
	}
	return features, rows.Err()
}

// GetExistingFeatureBarIds returns bar IDs that already have computed features.
// Only returns non-NULL bar_ids (aggregate timeframes have NULL bar_id).
func (r *FeatureRepo) GetExistingFeatureBarIds(ctx context.Context, tickerID int32, timeframe string, start, end *time.Time) ([]int64, error) {
	if !ValidTimeframes[timeframe] {
		return nil, fmt.Errorf("invalid timeframe %q", timeframe)
	}

	query := `SELECT bar_id FROM computed_features WHERE ticker_id = $1 AND timeframe = $2 AND bar_id IS NOT NULL`
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

	rows, err := r.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("querying existing feature bar IDs: %w", err)
	}
	defer rows.Close()

	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			return nil, fmt.Errorf("scanning bar_id: %w", err)
		}
		ids = append(ids, id)
	}
	return ids, rows.Err()
}

// GetExistingFeatureTimestamps returns timestamps that already have computed features.
// Works for all timeframes, including aggregates with NULL bar_id.
func (r *FeatureRepo) GetExistingFeatureTimestamps(ctx context.Context, tickerID int32, timeframe string, start, end *time.Time) ([]time.Time, error) {
	if !ValidTimeframes[timeframe] {
		return nil, fmt.Errorf("invalid timeframe %q", timeframe)
	}

	query := `SELECT timestamp FROM computed_features WHERE ticker_id = $1 AND timeframe = $2`
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

	rows, err := r.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("querying existing feature timestamps: %w", err)
	}
	defer rows.Close()

	var timestamps []time.Time
	for rows.Next() {
		var ts time.Time
		if err := rows.Scan(&ts); err != nil {
			return nil, fmt.Errorf("scanning timestamp: %w", err)
		}
		timestamps = append(timestamps, ts)
	}
	return timestamps, rows.Err()
}

// filterFeatures removes NaN/Inf values from a feature map before storing.
func filterFeatures(features map[string]float64) map[string]float64 {
	filtered := make(map[string]float64, len(features))
	for k, v := range features {
		if !math.IsNaN(v) && !math.IsInf(v, 0) {
			filtered[k] = v
		}
	}
	return filtered
}

// BulkUpsertFeatures inserts or updates computed features using pgx.Batch.
func (r *FeatureRepo) BulkUpsertFeatures(ctx context.Context, features []ComputedFeature) (int, error) {
	if len(features) == 0 {
		return 0, nil
	}

	const batchSize = 5000
	totalUpserted := 0

	for i := 0; i < len(features); i += batchSize {
		end := i + batchSize
		if end > len(features) {
			end = len(features)
		}
		chunk := features[i:end]

		batch := &pgx.Batch{}
		for _, f := range chunk {
			filtered := filterFeatures(f.Features)
			featJSON, err := json.Marshal(filtered)
			if err != nil {
				return totalUpserted, fmt.Errorf("marshaling features: %w", err)
			}

			batch.Queue(
				`INSERT INTO computed_features (bar_id, ticker_id, timeframe, timestamp, features, feature_version, model_id, state_id, state_prob, log_likelihood, created_at)
				 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
				 ON CONFLICT (ticker_id, timeframe, timestamp) DO UPDATE SET
				   features = EXCLUDED.features,
				   feature_version = EXCLUDED.feature_version,
				   bar_id = COALESCE(EXCLUDED.bar_id, computed_features.bar_id),
				   model_id = COALESCE(EXCLUDED.model_id, computed_features.model_id),
				   state_id = COALESCE(EXCLUDED.state_id, computed_features.state_id),
				   state_prob = COALESCE(EXCLUDED.state_prob, computed_features.state_prob),
				   log_likelihood = COALESCE(EXCLUDED.log_likelihood, computed_features.log_likelihood)`,
				f.BarID, f.TickerID, f.Timeframe, f.Timestamp,
				featJSON, f.FeatureVersion, f.ModelID, f.StateID, f.StateProb, f.LogLikelihood,
			)
		}

		results := r.pool.SendBatch(ctx, batch)
		for range chunk {
			tag, err := results.Exec()
			if err != nil {
				results.Close()
				return totalUpserted, fmt.Errorf("upserting feature: %w", err)
			}
			totalUpserted += int(tag.RowsAffected())
		}
		if err := results.Close(); err != nil {
			return totalUpserted, fmt.Errorf("closing batch: %w", err)
		}

		r.logger.Debug("Feature batch upsert complete",
			"chunk_size", len(chunk),
			"offset", i,
		)
	}

	return totalUpserted, nil
}

// StoreStates stores HMM/PCA model state assignments.
func (r *FeatureRepo) StoreStates(ctx context.Context, states []ComputedFeature, modelID string) (int, error) {
	if len(states) == 0 {
		return 0, nil
	}

	batch := &pgx.Batch{}
	for _, s := range states {
		batch.Queue(
			`UPDATE computed_features SET
			   model_id = $1,
			   state_id = $2,
			   state_prob = $3,
			   log_likelihood = $4
			 WHERE ticker_id = $5 AND timeframe = $6 AND timestamp = $7`,
			modelID, s.StateID, s.StateProb, s.LogLikelihood,
			s.TickerID, s.Timeframe, s.Timestamp,
		)
	}

	results := r.pool.SendBatch(ctx, batch)
	stored := 0
	for range states {
		tag, err := results.Exec()
		if err != nil {
			results.Close()
			return stored, fmt.Errorf("storing state: %w", err)
		}
		stored += int(tag.RowsAffected())
	}
	if err := results.Close(); err != nil {
		return stored, fmt.Errorf("closing batch: %w", err)
	}

	r.logger.Debug("StoreStates", "model_id", modelID, "stored", stored)
	return stored, nil
}

// GetStates returns state assignments for a ticker/timeframe/model.
func (r *FeatureRepo) GetStates(ctx context.Context, tickerID int32, timeframe, modelID string, start, end *time.Time) ([]ComputedFeature, error) {
	if !ValidTimeframes[timeframe] {
		return nil, fmt.Errorf("invalid timeframe %q", timeframe)
	}

	query := `SELECT id, bar_id, ticker_id, timeframe, timestamp, features, COALESCE(feature_version, ''), model_id, state_id, state_prob, log_likelihood, created_at
		 FROM computed_features WHERE ticker_id = $1 AND timeframe = $2 AND model_id = $3`
	args := []any{tickerID, timeframe, modelID}
	argIdx := 4

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
		return nil, fmt.Errorf("querying states: %w", err)
	}
	defer rows.Close()

	return scanFeatures(rows)
}

// GetLatestStates returns the most recent state assignments for a ticker/timeframe (all models).
func (r *FeatureRepo) GetLatestStates(ctx context.Context, tickerID int32, timeframe string) ([]ComputedFeature, error) {
	if !ValidTimeframes[timeframe] {
		return nil, fmt.Errorf("invalid timeframe %q", timeframe)
	}

	rows, err := r.pool.Query(ctx,
		`SELECT DISTINCT ON (model_id)
		   id, bar_id, ticker_id, timeframe, timestamp, features, COALESCE(feature_version, ''), model_id, state_id, state_prob, log_likelihood, created_at
		 FROM computed_features
		 WHERE ticker_id = $1 AND timeframe = $2 AND model_id IS NOT NULL
		 ORDER BY model_id, timestamp DESC`,
		tickerID, timeframe,
	)
	if err != nil {
		return nil, fmt.Errorf("querying latest states: %w", err)
	}
	defer rows.Close()

	return scanFeatures(rows)
}
