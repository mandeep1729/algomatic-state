package exits

import (
	"math"
	"testing"

	"github.com/algomatic/strats100/go-strats/pkg/types"
)

func makeStrategy(atrStop, atrTarget, trailing float64, timeBars int) *types.StrategyDef {
	return &types.StrategyDef{
		ID:              1,
		Name:            "test",
		ATRStopMult:     atrStop,
		ATRTargetMult:   atrTarget,
		TrailingATRMult: trailing,
		TimeStopBars:    timeBars,
	}
}

func TestStopLossLong(t *testing.T) {
	strat := makeStrategy(2.0, 0, 0, 0)
	em := NewExitManager(100.0, types.Long, 5.0, strat, types.RiskMedium)

	// StopDist = 2.0 * 1.5 * 5.0 = 15.0
	// Stop level = 100 - 15 = 85
	expectedStop := 2.0 * 1.5 * 5.0
	if math.Abs(em.StopDist-expectedStop) > 0.001 {
		t.Errorf("StopDist = %f, want %f", em.StopDist, expectedStop)
	}

	// Bar above stop: no exit
	reason := em.Check(105, 90, 102)
	if reason != "" {
		t.Errorf("expected no exit, got %q", reason)
	}

	// Bar hits stop
	reason = em.Check(102, 84, 86)
	if reason != "stop_loss" {
		t.Errorf("expected stop_loss, got %q", reason)
	}
}

func TestStopLossShort(t *testing.T) {
	strat := makeStrategy(2.0, 0, 0, 0)
	em := NewExitManager(100.0, types.Short, 5.0, strat, types.RiskMedium)

	// Stop level = 100 + 15 = 115
	reason := em.Check(110, 95, 98)
	if reason != "" {
		t.Errorf("expected no exit, got %q", reason)
	}

	reason = em.Check(116, 100, 102)
	if reason != "stop_loss" {
		t.Errorf("expected stop_loss, got %q", reason)
	}
}

func TestTargetLong(t *testing.T) {
	strat := makeStrategy(2.0, 3.0, 0, 0)
	em := NewExitManager(100.0, types.Long, 5.0, strat, types.RiskMedium)

	// TargetDist = 3.0 * 1.5 * 5.0 = 22.5
	// Target level = 100 + 22.5 = 122.5
	expectedTarget := 3.0 * 1.5 * 5.0
	if math.Abs(em.TargetDist-expectedTarget) > 0.001 {
		t.Errorf("TargetDist = %f, want %f", em.TargetDist, expectedTarget)
	}

	reason := em.Check(120, 98, 118)
	if reason != "" {
		t.Errorf("expected no exit, got %q", reason)
	}

	reason = em.Check(123, 115, 122)
	if reason != "target" {
		t.Errorf("expected target, got %q", reason)
	}
}

func TestTargetShort(t *testing.T) {
	strat := makeStrategy(2.0, 3.0, 0, 0)
	em := NewExitManager(100.0, types.Short, 5.0, strat, types.RiskMedium)

	// Target level = 100 - 22.5 = 77.5
	reason := em.Check(105, 80, 82)
	if reason != "" {
		t.Errorf("expected no exit, got %q", reason)
	}

	reason = em.Check(80, 76, 78)
	if reason != "target" {
		t.Errorf("expected target, got %q", reason)
	}
}

func TestTrailingStopLong(t *testing.T) {
	strat := makeStrategy(0, 0, 2.0, 0)
	em := NewExitManager(100.0, types.Long, 5.0, strat, types.RiskMedium)

	// TrailDist = 2.0 * 1.5 * 5.0 = 15.0
	// Initial trailing stop = 100 - 15 = 85

	// Bar 1: Price rises, low stays above initial trail (85)
	// high=108, low=98, close=106
	// newTrail = 108 - 15 = 93. 93 > 85, so trail = 93.
	// low=98 > 93, no exit.
	reason := em.Check(108, 98, 106)
	if reason != "" {
		t.Errorf("bar 1: expected no exit, got %q", reason)
	}

	// Bar 2: Price rises more, low stays above trail (93)
	// high=115, low=105, close=112
	// newTrail = 115 - 15 = 100. 100 > 93, trail = 100.
	// low=105 > 100, no exit.
	reason = em.Check(115, 105, 112)
	if reason != "" {
		t.Errorf("bar 2: expected no exit, got %q", reason)
	}

	// Bar 3: Price dips below trailing stop (100)
	// high=105, low=98, close=99
	// newTrail = 105 - 15 = 90. 90 < 100, trail stays 100.
	// low=98 <= 100, trailing stop triggered.
	reason = em.Check(105, 98, 99)
	if reason != "trailing_stop" {
		t.Errorf("bar 3: expected trailing_stop, got %q", reason)
	}
}

func TestTrailingStopShort(t *testing.T) {
	strat := makeStrategy(0, 0, 2.0, 0)
	em := NewExitManager(100.0, types.Short, 5.0, strat, types.RiskMedium)

	// Initial trailing stop = 100 + 15 = 115

	// Price moves down, trailing stop ratchets down
	reason := em.Check(98, 85, 87)
	if reason != "" {
		t.Errorf("expected no exit, got %q", reason)
	}
	// New trail: 85 + 15 = 100

	// Price bounces but stays below trail
	reason = em.Check(99, 88, 98)
	if reason != "" {
		t.Errorf("expected no exit, got %q", reason)
	}

	// Price exceeds trailing stop
	reason = em.Check(101, 95, 100)
	if reason != "trailing_stop" {
		t.Errorf("expected trailing_stop, got %q", reason)
	}
}

func TestTimeStop(t *testing.T) {
	strat := makeStrategy(0, 0, 0, 10)
	em := NewExitManager(100.0, types.Long, 5.0, strat, types.RiskMedium)

	// TimeLimit = int(10 * 1.0) = 10 (medium scale = 1.0)

	// Run for 9 bars, no exit
	for i := 0; i < 9; i++ {
		reason := em.Check(105, 95, 102)
		if reason != "" {
			t.Errorf("bar %d: expected no exit, got %q", i+1, reason)
		}
	}

	// Bar 10 triggers time stop
	reason := em.Check(105, 95, 102)
	if reason != "time_stop" {
		t.Errorf("expected time_stop at bar 10, got %q", reason)
	}
}

func TestTimeStopScaling(t *testing.T) {
	strat := makeStrategy(0, 0, 0, 10)

	// Low risk: TimeScale = 0.6, so limit = int(10 * 0.6) = 6
	emLow := NewExitManager(100.0, types.Long, 5.0, strat, types.RiskLow)
	if emLow.TimeLimit != 6 {
		t.Errorf("low risk TimeLimit = %d, want 6", emLow.TimeLimit)
	}

	// High risk: TimeScale = 1.5, so limit = int(10 * 1.5) = 15
	emHigh := NewExitManager(100.0, types.Long, 5.0, strat, types.RiskHigh)
	if emHigh.TimeLimit != 15 {
		t.Errorf("high risk TimeLimit = %d, want 15", emHigh.TimeLimit)
	}
}

func TestMaxDrawdownPct(t *testing.T) {
	strat := makeStrategy(0, 0, 0, 100)
	em := NewExitManager(100.0, types.Long, 5.0, strat, types.RiskMedium)

	// Price dips to 90 (worst), then recovers
	em.Check(105, 90, 102)
	em.Check(108, 98, 106)

	dd := em.MaxDrawdownPct()
	// (100 - 90) / 100 = 0.10
	if math.Abs(dd-0.10) > 0.001 {
		t.Errorf("MaxDrawdownPct = %f, want 0.10", dd)
	}
}

func TestMaxProfitPct(t *testing.T) {
	strat := makeStrategy(0, 0, 0, 100)
	em := NewExitManager(100.0, types.Long, 5.0, strat, types.RiskMedium)

	em.Check(120, 95, 115)
	em.Check(115, 100, 110)

	mfe := em.MaxProfitPct()
	// (120 - 100) / 100 = 0.20
	if math.Abs(mfe-0.20) > 0.001 {
		t.Errorf("MaxProfitPct = %f, want 0.20", mfe)
	}
}

func TestPnLStd(t *testing.T) {
	strat := makeStrategy(0, 0, 0, 100)
	em := NewExitManager(100.0, types.Long, 5.0, strat, types.RiskMedium)

	em.Check(105, 98, 102)
	em.Check(108, 99, 105)

	std := em.PnLStd()
	if std < 0 || math.IsNaN(std) {
		t.Errorf("PnLStd should be non-negative, got %f", std)
	}
}

func TestPnLStdNotEnoughBars(t *testing.T) {
	strat := makeStrategy(0, 0, 0, 100)
	em := NewExitManager(100.0, types.Long, 5.0, strat, types.RiskMedium)

	// Only 1 bar
	em.Check(105, 98, 102)
	std := em.PnLStd()
	if std != 0.0 {
		t.Errorf("PnLStd with 1 bar should be 0, got %f", std)
	}
}

func TestGetExitPrice(t *testing.T) {
	strat := makeStrategy(2.0, 3.0, 2.0, 0)
	em := NewExitManager(100.0, types.Long, 5.0, strat, types.RiskMedium)

	// Stop loss: entry - stopDist
	price := GetExitPrice("stop_loss", types.Long, 100.0, em, 95.0)
	expected := 100.0 - em.StopDist
	if math.Abs(price-expected) > 0.001 {
		t.Errorf("stop_loss exit price = %f, want %f", price, expected)
	}

	// Target: entry + targetDist
	price = GetExitPrice("target", types.Long, 100.0, em, 125.0)
	expected = 100.0 + em.TargetDist
	if math.Abs(price-expected) > 0.001 {
		t.Errorf("target exit price = %f, want %f", price, expected)
	}

	// Signal exit: use close
	price = GetExitPrice("signal_exit", types.Long, 100.0, em, 105.0)
	if math.Abs(price-105.0) > 0.001 {
		t.Errorf("signal exit price = %f, want 105.0", price)
	}

	// Time stop: use close
	price = GetExitPrice("time_stop", types.Long, 100.0, em, 103.0)
	if math.Abs(price-103.0) > 0.001 {
		t.Errorf("time_stop exit price = %f, want 103.0", price)
	}
}

func TestNoExitsConfigured(t *testing.T) {
	strat := makeStrategy(0, 0, 0, 0)
	em := NewExitManager(100.0, types.Long, 5.0, strat, types.RiskMedium)

	// Nothing configured, should never exit mechanically
	for i := 0; i < 100; i++ {
		reason := em.Check(120, 80, 100)
		if reason != "" {
			t.Errorf("bar %d: expected no exit, got %q", i+1, reason)
		}
	}
}

func TestStopLossPriority(t *testing.T) {
	// When both stop and target could trigger on same bar, stop should fire first
	strat := makeStrategy(2.0, 3.0, 0, 0)
	em := NewExitManager(100.0, types.Long, 5.0, strat, types.RiskMedium)

	// StopDist = 15, stop at 85
	// TargetDist = 22.5, target at 122.5
	// Bar that hits both: low <= 85 AND high >= 122.5
	reason := em.Check(123, 84, 100)
	if reason != "stop_loss" {
		t.Errorf("expected stop_loss (priority), got %q", reason)
	}
}
