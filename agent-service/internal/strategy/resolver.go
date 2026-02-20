package strategy

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"sync"

	"github.com/algomatic/agent-service/internal/repository"
	"github.com/algomatic/strats100/go-strats/pkg/dsl"
	"github.com/algomatic/strats100/go-strats/pkg/strategy"
	"github.com/algomatic/strats100/go-strats/pkg/types"
)

// cachedEntry holds a compiled strategy definition alongside its version
// for cache invalidation.
type cachedEntry struct {
	def     *types.StrategyDef
	version int
}

// Resolver bridges between DB strategy rows and compiled go-strats StrategyDef.
type Resolver struct {
	stratRepo *repository.StrategyRepo
	logger    *slog.Logger

	mu    sync.RWMutex
	cache map[int]*cachedEntry
}

// NewResolver creates a new Resolver.
func NewResolver(stratRepo *repository.StrategyRepo, logger *slog.Logger) *Resolver {
	return &Resolver{
		stratRepo: stratRepo,
		logger:    logger,
		cache:     make(map[int]*cachedEntry),
	}
}

// Resolve returns the compiled StrategyDef for a given DB strategy ID.
// For predefined strategies, it looks up the go-strats registry.
// For custom strategies, it compiles conditions from the JSONB DSL.
// Results are cached by version — a version bump triggers recompilation.
func (r *Resolver) Resolve(ctx context.Context, strategyID int) (*types.StrategyDef, error) {
	// Always load the row to check version (cheap PK lookup).
	row, err := r.stratRepo.GetStrategy(ctx, strategyID)
	if err != nil {
		return nil, fmt.Errorf("loading strategy %d from DB: %w", strategyID, err)
	}

	// Check cache with version comparison.
	r.mu.RLock()
	if entry, ok := r.cache[strategyID]; ok && entry.version == row.Version {
		r.mu.RUnlock()
		return entry.def, nil
	}
	r.mu.RUnlock()

	// Predefined strategy: resolve from go-strats registry.
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

		r.mu.Lock()
		r.cache[strategyID] = &cachedEntry{def: def, version: row.Version}
		r.mu.Unlock()

		return def, nil
	}

	// Custom strategy: compile from JSONB DSL conditions.
	def, err := compileCustomStrategy(row)
	if err != nil {
		return nil, fmt.Errorf("compiling custom strategy %d (%s): %w", strategyID, row.Name, err)
	}

	r.logger.Info("Compiled custom strategy from DSL",
		"db_id", strategyID, "name", row.Name, "version", row.Version,
	)

	r.mu.Lock()
	r.cache[strategyID] = &cachedEntry{def: def, version: row.Version}
	r.mu.Unlock()

	return def, nil
}

// compileCustomStrategy builds a StrategyDef from the JSONB condition columns.
func compileCustomStrategy(row *repository.AgentStrategyRow) (*types.StrategyDef, error) {
	entryLong, err := dsl.ParseAndCompile(row.EntryLong)
	if err != nil {
		return nil, fmt.Errorf("entry_long: %w", err)
	}
	entryShort, err := dsl.ParseAndCompile(row.EntryShort)
	if err != nil {
		return nil, fmt.Errorf("entry_short: %w", err)
	}
	exitLong, err := dsl.ParseAndCompile(row.ExitLong)
	if err != nil {
		return nil, fmt.Errorf("exit_long: %w", err)
	}
	exitShort, err := dsl.ParseAndCompile(row.ExitShort)
	if err != nil {
		return nil, fmt.Errorf("exit_short: %w", err)
	}

	// Collect required features from all condition trees.
	var allNodes []dsl.ConditionNode
	for _, raw := range [][]byte{row.EntryLong, row.EntryShort, row.ExitLong, row.ExitShort} {
		if len(raw) == 0 || string(raw) == "null" {
			continue
		}
		var nodes []dsl.ConditionNode
		// Already validated by ParseAndCompile, ignore parse errors here.
		if jsonErr := json.Unmarshal(raw, &nodes); jsonErr == nil {
			allNodes = append(allNodes, nodes...)
		}
	}
	features := dsl.ExtractRequiredFeatures(allNodes)

	var atrStop, atrTarget, trailingATR float64
	var timeStopBars int
	if row.ATRStopMult != nil {
		atrStop = *row.ATRStopMult
	}
	if row.ATRTargetMult != nil {
		atrTarget = *row.ATRTargetMult
	}
	if row.TrailingATRMult != nil {
		trailingATR = *row.TrailingATRMult
	}
	if row.TimeStopBars != nil {
		timeStopBars = *row.TimeStopBars
	}

	dir := types.LongShort
	switch row.Direction {
	case "long_only":
		dir = types.LongOnly
	case "short_only":
		dir = types.ShortOnly
	}

	return &types.StrategyDef{
		ID:                 row.ID,
		Name:               row.Name,
		DisplayName:        row.DisplayName,
		Category:           row.Category,
		Direction:          dir,
		EntryLong:          entryLong,
		EntryShort:         entryShort,
		ExitLong:           exitLong,
		ExitShort:          exitShort,
		ATRStopMult:        atrStop,
		ATRTargetMult:      atrTarget,
		TrailingATRMult:    trailingATR,
		TimeStopBars:       timeStopBars,
		RequiredIndicators: features,
	}, nil
}

// ClearCache removes all cached strategy definitions.
func (r *Resolver) ClearCache() {
	r.mu.Lock()
	r.cache = make(map[int]*cachedEntry)
	r.mu.Unlock()
	r.logger.Debug("Strategy cache cleared")
}
