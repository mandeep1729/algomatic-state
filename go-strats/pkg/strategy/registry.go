// Package strategy provides the strategy registry with all 100 strategy definitions.
//
// Mirrors the Python registry in src/strats_prob/registry.py and all
// strategy definitions in src/strats_prob/strategies/.
package strategy

import (
	"log/slog"
	"sort"
	"sync"

	"github.com/algomatic/strats100/go-strats/pkg/types"
)

var (
	mu            sync.RWMutex
	strategiesByID   = make(map[int]*types.StrategyDef)
	strategiesByName = make(map[string]*types.StrategyDef)
)

// Register adds a strategy to the registry.
func Register(s *types.StrategyDef) {
	mu.Lock()
	defer mu.Unlock()
	strategiesByID[s.ID] = s
	strategiesByName[s.Name] = s
}

// RegisterAll adds multiple strategies to the registry.
func RegisterAll(strategies []*types.StrategyDef) int {
	mu.Lock()
	defer mu.Unlock()
	count := 0
	for _, s := range strategies {
		strategiesByID[s.ID] = s
		strategiesByName[s.Name] = s
		count++
	}
	slog.Info("Registered strategies", "count", count, "total", len(strategiesByID))
	return count
}

// Get returns a strategy by ID, or nil if not found.
func Get(id int) *types.StrategyDef {
	mu.RLock()
	defer mu.RUnlock()
	return strategiesByID[id]
}

// GetByName returns a strategy by name, or nil if not found.
func GetByName(name string) *types.StrategyDef {
	mu.RLock()
	defer mu.RUnlock()
	return strategiesByName[name]
}

// GetAll returns all registered strategies sorted by ID.
func GetAll() []*types.StrategyDef {
	mu.RLock()
	defer mu.RUnlock()
	result := make([]*types.StrategyDef, 0, len(strategiesByID))
	for _, s := range strategiesByID {
		result = append(result, s)
	}
	sort.Slice(result, func(i, j int) bool {
		return result[i].ID < result[j].ID
	})
	return result
}

// GetByCategory returns all strategies of a given category sorted by ID.
func GetByCategory(category string) []*types.StrategyDef {
	mu.RLock()
	defer mu.RUnlock()
	var result []*types.StrategyDef
	for _, s := range strategiesByID {
		if s.Category == category {
			result = append(result, s)
		}
	}
	sort.Slice(result, func(i, j int) bool {
		return result[i].ID < result[j].ID
	})
	return result
}

// Clear removes all registered strategies (useful for testing).
func Clear() {
	mu.Lock()
	defer mu.Unlock()
	strategiesByID = make(map[int]*types.StrategyDef)
	strategiesByName = make(map[string]*types.StrategyDef)
}

// Count returns the number of registered strategies.
func Count() int {
	mu.RLock()
	defer mu.RUnlock()
	return len(strategiesByID)
}
