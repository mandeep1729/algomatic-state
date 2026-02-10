package strategy

import (
	"testing"

	"github.com/algomatic/strats100/go-strats/pkg/types"
)

func TestRegistryRegistersAll100Strategies(t *testing.T) {
	// The init() function auto-registers all strategies.
	// Verify the count.
	count := Count()
	if count != 100 {
		t.Errorf("expected 100 registered strategies, got %d", count)
	}
}

func TestGetByID(t *testing.T) {
	strat := Get(1)
	if strat == nil {
		t.Fatal("strategy 1 not found")
	}
	if strat.Name != "ema20_ema50_trend_cross" {
		t.Errorf("strategy 1 name = %q, want ema20_ema50_trend_cross", strat.Name)
	}
}

func TestGetByIDNotFound(t *testing.T) {
	strat := Get(999)
	if strat != nil {
		t.Error("expected nil for non-existent strategy ID")
	}
}

func TestGetByName(t *testing.T) {
	strat := GetByName("rsi_oversold_bounce")
	if strat == nil {
		t.Fatal("strategy rsi_oversold_bounce not found")
	}
	if strat.ID != 26 {
		t.Errorf("strategy ID = %d, want 26", strat.ID)
	}
}

func TestGetByNameNotFound(t *testing.T) {
	strat := GetByName("nonexistent_strategy")
	if strat != nil {
		t.Error("expected nil for non-existent strategy name")
	}
}

func TestGetAll(t *testing.T) {
	all := GetAll()
	if len(all) != 100 {
		t.Errorf("GetAll returned %d strategies, want 100", len(all))
	}

	// Verify sorted by ID
	for i := 1; i < len(all); i++ {
		if all[i].ID <= all[i-1].ID {
			t.Errorf("strategies not sorted by ID: %d <= %d at index %d", all[i].ID, all[i-1].ID, i)
		}
	}
}

func TestGetByCategory(t *testing.T) {
	categories := map[string]int{
		"trend":          25,
		"mean_reversion": 25,
		"breakout":       20,
		"volume_flow":    10,
		"pattern":        10,
		"regime":         10,
	}

	for category, expectedCount := range categories {
		strats := GetByCategory(category)
		if len(strats) != expectedCount {
			t.Errorf("category %q: got %d strategies, want %d", category, len(strats), expectedCount)
		}
	}
}

func TestAllStrategiesHaveRequiredFields(t *testing.T) {
	all := GetAll()
	for _, s := range all {
		if s.ID < 1 || s.ID > 100 {
			t.Errorf("strategy ID %d out of range [1,100]", s.ID)
		}
		if s.Name == "" {
			t.Errorf("strategy %d has empty name", s.ID)
		}
		if s.DisplayName == "" {
			t.Errorf("strategy %d (%s) has empty display name", s.ID, s.Name)
		}
		if s.Category == "" {
			t.Errorf("strategy %d (%s) has empty category", s.ID, s.Name)
		}
		if s.Direction == "" {
			t.Errorf("strategy %d (%s) has empty direction", s.ID, s.Name)
		}
		if len(s.Tags) == 0 {
			t.Errorf("strategy %d (%s) has no tags", s.ID, s.Name)
		}

		// At least one entry condition should exist
		hasEntry := len(s.EntryLong) > 0 || len(s.EntryShort) > 0
		if !hasEntry {
			t.Errorf("strategy %d (%s) has no entry conditions", s.ID, s.Name)
		}

		// Direction-specific checks
		switch s.Direction {
		case types.LongOnly:
			if len(s.EntryLong) == 0 {
				t.Errorf("strategy %d (%s) is LongOnly but has no EntryLong", s.ID, s.Name)
			}
		case types.ShortOnly:
			if len(s.EntryShort) == 0 {
				t.Errorf("strategy %d (%s) is ShortOnly but has no EntryShort", s.ID, s.Name)
			}
		case types.LongShort:
			if len(s.EntryLong) == 0 {
				t.Errorf("strategy %d (%s) is LongShort but has no EntryLong", s.ID, s.Name)
			}
			if len(s.EntryShort) == 0 {
				t.Errorf("strategy %d (%s) is LongShort but has no EntryShort", s.ID, s.Name)
			}
		}
	}
}

func TestAllStrategyIDsAreUnique(t *testing.T) {
	all := GetAll()
	seen := make(map[int]string)
	for _, s := range all {
		if other, ok := seen[s.ID]; ok {
			t.Errorf("duplicate strategy ID %d: %q and %q", s.ID, other, s.Name)
		}
		seen[s.ID] = s.Name
	}
}

func TestAllStrategyNamesAreUnique(t *testing.T) {
	all := GetAll()
	seen := make(map[string]int)
	for _, s := range all {
		if otherID, ok := seen[s.Name]; ok {
			t.Errorf("duplicate strategy name %q: IDs %d and %d", s.Name, otherID, s.ID)
		}
		seen[s.Name] = s.ID
	}
}

func TestAllStrategiesHaveATRInRequiredIndicators(t *testing.T) {
	all := GetAll()
	for _, s := range all {
		hasATR := false
		for _, ind := range s.RequiredIndicators {
			if ind == "atr_14" {
				hasATR = true
				break
			}
		}
		if !hasATR {
			t.Errorf("strategy %d (%s) missing atr_14 in RequiredIndicators", s.ID, s.Name)
		}
	}
}

func TestStrategyCoverageOfCategories(t *testing.T) {
	all := GetAll()
	categories := make(map[string]bool)
	for _, s := range all {
		categories[s.Category] = true
	}

	expected := []string{"trend", "mean_reversion", "breakout", "volume_flow", "pattern", "regime"}
	for _, cat := range expected {
		if !categories[cat] {
			t.Errorf("missing category: %s", cat)
		}
	}
}

func TestStrategyCoverageOfDirections(t *testing.T) {
	all := GetAll()
	directions := make(map[types.StrategyDirection]bool)
	for _, s := range all {
		directions[s.Direction] = true
	}

	if !directions[types.LongOnly] {
		t.Error("no LongOnly strategies found")
	}
	if !directions[types.ShortOnly] {
		t.Error("no ShortOnly strategies found")
	}
	if !directions[types.LongShort] {
		t.Error("no LongShort strategies found")
	}
}

func TestStrategyIDRange(t *testing.T) {
	all := GetAll()

	// Verify all IDs from 1-100 are present
	idSet := make(map[int]bool)
	for _, s := range all {
		idSet[s.ID] = true
	}

	for id := 1; id <= 100; id++ {
		if !idSet[id] {
			t.Errorf("missing strategy ID %d", id)
		}
	}
}

func TestStrategyPhilosophyPresent(t *testing.T) {
	all := GetAll()
	for _, s := range all {
		if s.Philosophy == "" {
			t.Errorf("strategy %d (%s) has empty philosophy", s.ID, s.Name)
		}
	}
}
