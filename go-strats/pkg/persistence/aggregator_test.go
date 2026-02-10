package persistence

import (
	"math"
	"testing"
	"time"

	"github.com/algomatic/strats100/go-strats/pkg/types"
)

func TestAggregateTrades_Empty(t *testing.T) {
	results := AggregateTrades(nil, 1, "AAPL", "1Min", "medium", "run1",
		time.Now(), time.Now())
	if results != nil {
		t.Errorf("expected nil for empty trades, got %d results", len(results))
	}
}

func TestAggregateTrades_SingleTrade(t *testing.T) {
	entry := time.Date(2025, 3, 15, 10, 30, 0, 0, time.UTC)
	exit := time.Date(2025, 3, 15, 11, 0, 0, 0, time.UTC)
	trades := []types.Trade{
		{
			EntryTime: entry, ExitTime: exit,
			EntryPrice: 100.0, ExitPrice: 102.0,
			Direction: types.Long, PnLPct: 0.02,
			BarsHeld: 30, MaxDrawdownPct: 0.005, MaxProfitPct: 0.025,
			PnLStd: 0.001,
		},
	}

	results := AggregateTrades(trades, 42, "aapl", "1Hour", "high", "run123",
		entry, exit)

	if len(results) != 1 {
		t.Fatalf("expected 1 group, got %d", len(results))
	}

	r := results[0]
	if r.Symbol != "AAPL" {
		t.Errorf("expected symbol AAPL, got %s", r.Symbol)
	}
	if r.StrategyID != 42 {
		t.Errorf("expected strategy_id 42, got %d", r.StrategyID)
	}
	if r.Timeframe != "1Hour" {
		t.Errorf("expected timeframe 1Hour, got %s", r.Timeframe)
	}
	if r.RiskProfile != "high" {
		t.Errorf("expected risk_profile high, got %s", r.RiskProfile)
	}
	if r.RunID != "run123" {
		t.Errorf("expected run_id run123, got %s", r.RunID)
	}

	// Dimensions
	expectedDay := time.Date(2025, 3, 15, 0, 0, 0, 0, time.UTC)
	if !r.OpenDay.Equal(expectedDay) {
		t.Errorf("expected open_day %v, got %v", expectedDay, r.OpenDay)
	}
	if r.OpenHour != 10 {
		t.Errorf("expected open_hour 10, got %d", r.OpenHour)
	}
	if r.LongShort != "long" {
		t.Errorf("expected long_short 'long', got %s", r.LongShort)
	}

	// Aggregations
	if r.NumTrades != 1 {
		t.Errorf("expected num_trades 1, got %d", r.NumTrades)
	}
	if r.PnLMean != 0.02 {
		t.Errorf("expected pnl_mean 0.02, got %f", r.PnLMean)
	}
	if r.PnLStd != 0.0 {
		t.Errorf("expected pnl_std 0.0 for single trade, got %f", r.PnLStd)
	}
	if r.MaxDrawdown != 0.005 {
		t.Errorf("expected max_drawdown 0.005, got %f", r.MaxDrawdown)
	}
	if r.MaxProfit != 0.025 {
		t.Errorf("expected max_profit 0.025, got %f", r.MaxProfit)
	}
}

func TestAggregateTrades_MultipleGroups(t *testing.T) {
	day1Hour10 := time.Date(2025, 3, 15, 10, 0, 0, 0, time.UTC)
	day1Hour14 := time.Date(2025, 3, 15, 14, 0, 0, 0, time.UTC)
	day2Hour10 := time.Date(2025, 3, 16, 10, 0, 0, 0, time.UTC)

	trades := []types.Trade{
		// Group 1: day1, hour10, long
		{EntryTime: day1Hour10, ExitTime: day1Hour10.Add(time.Hour),
			EntryPrice: 100, ExitPrice: 101, Direction: types.Long,
			PnLPct: 0.01, MaxDrawdownPct: 0.002, MaxProfitPct: 0.015},
		{EntryTime: day1Hour10.Add(5 * time.Minute), ExitTime: day1Hour10.Add(time.Hour),
			EntryPrice: 100, ExitPrice: 103, Direction: types.Long,
			PnLPct: 0.03, MaxDrawdownPct: 0.001, MaxProfitPct: 0.035},
		// Group 2: day1, hour14, short
		{EntryTime: day1Hour14, ExitTime: day1Hour14.Add(30 * time.Minute),
			EntryPrice: 100, ExitPrice: 98, Direction: types.Short,
			PnLPct: 0.02, MaxDrawdownPct: 0.003, MaxProfitPct: 0.025},
		// Group 3: day2, hour10, long (different day)
		{EntryTime: day2Hour10, ExitTime: day2Hour10.Add(time.Hour),
			EntryPrice: 100, ExitPrice: 99, Direction: types.Long,
			PnLPct: -0.01, MaxDrawdownPct: 0.015, MaxProfitPct: 0.005},
	}

	results := AggregateTrades(trades, 1, "SPY", "15Min", "low", "run2",
		day1Hour10, day2Hour10.Add(2*time.Hour))

	if len(results) != 3 {
		t.Fatalf("expected 3 groups, got %d", len(results))
	}

	// Build lookup by group key for deterministic assertions
	grouped := make(map[GroupKey]AggregatedResult)
	for _, r := range results {
		key := GroupKey{OpenDay: r.OpenDay, OpenHour: r.OpenHour, LongShort: r.LongShort}
		grouped[key] = r
	}

	// Group 1: 2 trades, day 15, hour 10, long
	g1Key := GroupKey{
		OpenDay:   time.Date(2025, 3, 15, 0, 0, 0, 0, time.UTC),
		OpenHour:  10,
		LongShort: "long",
	}
	g1, ok := grouped[g1Key]
	if !ok {
		t.Fatal("missing group: day15/hour10/long")
	}
	if g1.NumTrades != 2 {
		t.Errorf("g1: expected 2 trades, got %d", g1.NumTrades)
	}
	expectedMean := (0.01 + 0.03) / 2
	if math.Abs(g1.PnLMean-expectedMean) > 1e-10 {
		t.Errorf("g1: expected pnl_mean %f, got %f", expectedMean, g1.PnLMean)
	}
	if g1.PnLStd == 0.0 {
		t.Error("g1: pnl_std should be > 0 for 2 trades")
	}
	// Max drawdown should be max(0.002, 0.001) = 0.002
	if g1.MaxDrawdown != 0.002 {
		t.Errorf("g1: expected max_drawdown 0.002, got %f", g1.MaxDrawdown)
	}
	// Max profit should be max(0.015, 0.035) = 0.035
	if g1.MaxProfit != 0.035 {
		t.Errorf("g1: expected max_profit 0.035, got %f", g1.MaxProfit)
	}

	// Group 2: 1 trade, day 15, hour 14, short
	g2Key := GroupKey{
		OpenDay:   time.Date(2025, 3, 15, 0, 0, 0, 0, time.UTC),
		OpenHour:  14,
		LongShort: "short",
	}
	g2, ok := grouped[g2Key]
	if !ok {
		t.Fatal("missing group: day15/hour14/short")
	}
	if g2.NumTrades != 1 {
		t.Errorf("g2: expected 1 trade, got %d", g2.NumTrades)
	}

	// Group 3: different day — verifies day grouping is by full date
	g3Key := GroupKey{
		OpenDay:   time.Date(2025, 3, 16, 0, 0, 0, 0, time.UTC),
		OpenHour:  10,
		LongShort: "long",
	}
	_, ok = grouped[g3Key]
	if !ok {
		t.Fatal("missing group: day16/hour10/long — days not properly separated")
	}
}

func TestAggregateTrades_StdDevComputation(t *testing.T) {
	entry := time.Date(2025, 1, 1, 9, 0, 0, 0, time.UTC)
	exit := entry.Add(time.Hour)

	trades := []types.Trade{
		{EntryTime: entry, ExitTime: exit, EntryPrice: 100, Direction: types.Long,
			PnLPct: 0.01, MaxDrawdownPct: 0.001, MaxProfitPct: 0.01},
		{EntryTime: entry.Add(time.Minute), ExitTime: exit, EntryPrice: 100, Direction: types.Long,
			PnLPct: 0.03, MaxDrawdownPct: 0.001, MaxProfitPct: 0.03},
		{EntryTime: entry.Add(2 * time.Minute), ExitTime: exit, EntryPrice: 100, Direction: types.Long,
			PnLPct: 0.02, MaxDrawdownPct: 0.001, MaxProfitPct: 0.02},
	}

	results := AggregateTrades(trades, 1, "AAPL", "1Min", "medium", "run1",
		entry, exit)

	if len(results) != 1 {
		t.Fatalf("expected 1 group, got %d", len(results))
	}

	r := results[0]
	// Population std dev of [0.01, 0.03, 0.02] = sqrt(var) where var = mean of squared deviations
	// mean = 0.02, deviations = [-0.01, 0.01, 0], var = (0.0001+0.0001+0)/3 = 0.0000666...
	// std = sqrt(0.0000666...) ≈ 0.008165
	expectedStd := math.Sqrt(((0.01-0.02)*(0.01-0.02) + (0.03-0.02)*(0.03-0.02) + (0.02-0.02)*(0.02-0.02)) / 3)
	if math.Abs(r.PnLStd-expectedStd) > 1e-10 {
		t.Errorf("expected pnl_std %f, got %f", expectedStd, r.PnLStd)
	}
}

func TestBuildTradeRecords(t *testing.T) {
	entry := time.Date(2025, 3, 15, 10, 0, 0, 0, time.UTC)
	exit := entry.Add(time.Hour)

	trades := []types.Trade{
		{
			EntryTime: entry, ExitTime: exit,
			EntryPrice: 150.0, ExitPrice: 153.0,
			Direction: types.Long, PnLPct: 0.02,
			BarsHeld: 60, MaxDrawdownPct: 0.005, MaxProfitPct: 0.025,
			PnLStd: 0.001, ExitReason: "target",
			EntryJustification: "EMA20 crossed above EMA50",
			ExitJustification:  "ATR target hit at 153.00",
		},
	}

	records := BuildTradeRecords(trades, "aapl")

	if len(records) != 1 {
		t.Fatalf("expected 1 record, got %d", len(records))
	}

	r := records[0]
	if r.Ticker != "AAPL" {
		t.Errorf("expected ticker AAPL, got %s", r.Ticker)
	}
	if r.Direction != "long" {
		t.Errorf("expected direction long, got %s", r.Direction)
	}
	// PnL in currency = pnl_pct * entry_price = 0.02 * 150 = 3.0
	expectedPnL := 0.02 * 150.0
	if math.Abs(r.PnL-expectedPnL) > 1e-10 {
		t.Errorf("expected pnl %f, got %f", expectedPnL, r.PnL)
	}
	if r.OpenJustification != "EMA20 crossed above EMA50" {
		t.Errorf("unexpected open_justification: %s", r.OpenJustification)
	}
	if r.ResultID != 0 {
		t.Errorf("expected result_id 0 (unset), got %d", r.ResultID)
	}
}

func TestMapTradesToResults(t *testing.T) {
	entry1 := time.Date(2025, 3, 15, 10, 30, 0, 0, time.UTC)
	entry2 := time.Date(2025, 3, 15, 14, 0, 0, 0, time.UTC)
	exit := entry1.Add(time.Hour)

	engineTrades := []types.Trade{
		{EntryTime: entry1, ExitTime: exit, Direction: types.Long, EntryPrice: 100, PnLPct: 0.01},
		{EntryTime: entry2, ExitTime: exit, Direction: types.Short, EntryPrice: 100, PnLPct: -0.01},
	}
	tradeRecords := BuildTradeRecords(engineTrades, "AAPL")

	resultIDMap := map[GroupKey]int64{
		{OpenDay: time.Date(2025, 3, 15, 0, 0, 0, 0, time.UTC), OpenHour: 10, LongShort: "long"}: 100,
		// Note: hour 14 short is NOT in the map — should be unmatched
	}

	matched, unmatched := MapTradesToResults(tradeRecords, engineTrades, resultIDMap)

	if len(matched) != 1 {
		t.Fatalf("expected 1 matched, got %d", len(matched))
	}
	if unmatched != 1 {
		t.Errorf("expected 1 unmatched, got %d", unmatched)
	}
	if matched[0].ResultID != 100 {
		t.Errorf("expected result_id 100, got %d", matched[0].ResultID)
	}
}

func TestNormalizeDirection(t *testing.T) {
	cases := []struct {
		input    string
		expected string
	}{
		{"long", "long"},
		{"short", "short"},
		{"long_only", "long_"},
		{"", ""},
	}
	for _, tc := range cases {
		got := normalizeDirection(tc.input)
		if got != tc.expected {
			t.Errorf("normalizeDirection(%q) = %q, want %q", tc.input, got, tc.expected)
		}
	}
}

func TestTruncateToDate(t *testing.T) {
	ts := time.Date(2025, 10, 30, 14, 25, 33, 123456, time.UTC)
	date := truncateToDate(ts)
	expected := time.Date(2025, 10, 30, 0, 0, 0, 0, time.UTC)
	if !date.Equal(expected) {
		t.Errorf("truncateToDate(%v) = %v, want %v", ts, date, expected)
	}
}

func TestMean(t *testing.T) {
	if m := mean(nil); m != 0 {
		t.Errorf("mean(nil) = %f, want 0", m)
	}
	if m := mean([]float64{2, 4, 6}); m != 4 {
		t.Errorf("mean([2,4,6]) = %f, want 4", m)
	}
}

func TestStddev(t *testing.T) {
	if s := stddev(nil); s != 0 {
		t.Errorf("stddev(nil) = %f, want 0", s)
	}
	if s := stddev([]float64{5}); s != 0 {
		t.Errorf("stddev([5]) = %f, want 0", s)
	}
	// stddev([1, 3]) = sqrt(((1-2)^2 + (3-2)^2) / 2) = sqrt(1) = 1
	if s := stddev([]float64{1, 3}); math.Abs(s-1.0) > 1e-10 {
		t.Errorf("stddev([1,3]) = %f, want 1.0", s)
	}
}

func TestAggregateTrades_AllLosingTrades(t *testing.T) {
	entry := time.Date(2025, 5, 1, 9, 30, 0, 0, time.UTC)
	exit := entry.Add(time.Hour)

	trades := []types.Trade{
		{EntryTime: entry, ExitTime: exit, EntryPrice: 100, Direction: types.Long,
			PnLPct: -0.02, MaxDrawdownPct: 0.025, MaxProfitPct: 0.001},
		{EntryTime: entry.Add(time.Minute), ExitTime: exit, EntryPrice: 100, Direction: types.Long,
			PnLPct: -0.05, MaxDrawdownPct: 0.06, MaxProfitPct: 0.002},
	}

	results := AggregateTrades(trades, 1, "AAPL", "1Min", "medium", "run1",
		entry, exit)

	if len(results) != 1 {
		t.Fatalf("expected 1 group, got %d", len(results))
	}

	r := results[0]
	expectedMean := (-0.02 + -0.05) / 2
	if math.Abs(r.PnLMean-expectedMean) > 1e-10 {
		t.Errorf("expected pnl_mean %f, got %f", expectedMean, r.PnLMean)
	}
	if r.MaxDrawdown != 0.06 {
		t.Errorf("expected max_drawdown 0.06, got %f", r.MaxDrawdown)
	}
}
