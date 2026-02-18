package strategy

import (
	"context"
	"fmt"
	"log/slog"
	"sync"

	"github.com/algomatic/agent-service/internal/repository"
	"github.com/algomatic/strats100/go-strats/pkg/strategy"
	"github.com/algomatic/strats100/go-strats/pkg/types"
)

// Resolver bridges between DB strategy rows and compiled go-strats StrategyDef.
type Resolver struct {
	stratRepo *repository.StrategyRepo
	logger    *slog.Logger

	mu    sync.RWMutex
	cache map[int]*types.StrategyDef
}

// NewResolver creates a new Resolver.
func NewResolver(stratRepo *repository.StrategyRepo, logger *slog.Logger) *Resolver {
	return &Resolver{
		stratRepo: stratRepo,
		logger:    logger,
		cache:     make(map[int]*types.StrategyDef),
	}
}

// Resolve returns the compiled StrategyDef for a given DB strategy ID.
// For predefined strategies, it looks up the go-strats registry.
// Results are cached in memory.
func (r *Resolver) Resolve(ctx context.Context, strategyID int) (*types.StrategyDef, error) {
	// Check cache first
	r.mu.RLock()
	if def, ok := r.cache[strategyID]; ok {
		r.mu.RUnlock()
		return def, nil
	}
	r.mu.RUnlock()

	// Load strategy row from DB
	row, err := r.stratRepo.GetStrategy(ctx, strategyID)
	if err != nil {
		return nil, fmt.Errorf("loading strategy %d from DB: %w", strategyID, err)
	}

	// Predefined strategy: resolve from go-strats registry
	if row.IsPredefined && row.SourceStrategyID != nil {
		sourceID := *row.SourceStrategyID
		def := strategy.Get(sourceID)
		if def == nil {
			return nil, fmt.Errorf(
				"predefined strategy %d references go-strats ID %d which is not registered",
				strategyID, sourceID,
			)
		}

		r.logger.Debug("Resolved predefined strategy",
			"db_id", strategyID, "source_id", sourceID, "name", def.Name,
		)

		// Cache it
		r.mu.Lock()
		r.cache[strategyID] = def
		r.mu.Unlock()

		return def, nil
	}

	// Custom strategies with JSON conditions (deferred to future phase)
	return nil, fmt.Errorf(
		"custom strategy %d (%s) not yet supported — only predefined strategies are available",
		strategyID, row.Name,
	)
}

// ClearCache removes all cached strategy definitions.
func (r *Resolver) ClearCache() {
	r.mu.Lock()
	r.cache = make(map[int]*types.StrategyDef)
	r.mu.Unlock()
	r.logger.Debug("Strategy cache cleared")
}
