package engine

import (
	"log/slog"
	"math"
	"os"
	"testing"
	"time"

	"github.com/algomatic/strats100/go-strats/pkg/types"
)

func newTestLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelWarn}))
}

// makeBars generates bar data with a linear price series and ATR indicator.
func makeBars(n int, startPrice, step float64) []types.BarData {
	bars := make([]types.BarData, n)
	for i := 0; i < n; i++ {
		price := startPrice + float64(i)*step
		bars[i] = types.BarData{
			Bar: types.Bar{
				Timestamp: time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC).Add(time.Duration(i) * time.Hour),
				Open:      price - 0.2,
				High:      price + 1.0,
				Low:       price - 1.0,
				Close:     price,
				Volume:    1000,
			},
			Indicators: types.IndicatorRow{
				"atr_14": 2.0,
			},
		}
	}
	return bars
}

func TestEmptyBars(t *testing.T) {
	strat := &types.StrategyDef{
		ID:        1,
		Name:      "test",
		Direction: types.LongShort,
		EntryLong: []types.ConditionFn{func(bars []types.BarData, idx int) bool { return true }},
	}
	eng := NewProbeEngine(strat, types.RiskMedium, newTestLogger())
	trades := eng.Run(nil)
	if len(trades) != 0 {
		t.Error("expected no trades from empty bars")
	}
}

func TestSingleBarNoTrade(t *testing.T) {
	bars := makeBars(1, 100, 1)
	strat := &types.StrategyDef{
		ID:        1,
		Name:      "test",
		Direction: types.LongShort,
		EntryLong: []types.ConditionFn{func(bars []types.BarData, idx int) bool { return true }},
	}
	eng := NewProbeEngine(strat, types.RiskMedium, newTestLogger())
	trades := eng.Run(bars)
	// Signal on bar 0, but no bar 1 to enter on
	// Wait actually i < nBars-1 check prevents signal on last bar
	if len(trades) != 0 {
		t.Errorf("expected 0 trades from single bar, got %d", len(trades))
	}
}

func TestFillOnNextBar(t *testing.T) {
	// Create bars where entry signal fires on bar 1, entry should happen at bar 2's open
	bars := makeBars(20, 100, 0.5)

	signalFired := false
	strat := &types.StrategyDef{
		ID:        1,
		Name:      "test",
		Direction: types.LongOnly,
		EntryLong: []types.ConditionFn{
			func(bars []types.BarData, idx int) bool {
				if idx == 1 && !signalFired {
					signalFired = true
					return true
				}
				return false
			},
		},
		ATRStopMult: 2.0,
		TimeStopBars: 5,
	}

	eng := NewProbeEngine(strat, types.RiskMedium, newTestLogger())
	trades := eng.Run(bars)

	if len(trades) != 1 {
		t.Fatalf("expected 1 trade, got %d", len(trades))
	}

	trade := trades[0]
	// Entry should be at bar 2's open price
	expectedEntry := bars[2].Bar.Open
	if math.Abs(trade.EntryPrice-expectedEntry) > 0.001 {
		t.Errorf("entry price = %f, want %f (bar 2 open)", trade.EntryPrice, expectedEntry)
	}

	if trade.Direction != types.Long {
		t.Errorf("direction = %s, want long", trade.Direction)
	}
}

func TestSignalExitLong(t *testing.T) {
	bars := makeBars(20, 100, 0.5)

	entrySignaled := false
	strat := &types.StrategyDef{
		ID:        1,
		Name:      "test",
		Direction: types.LongOnly,
		EntryLong: []types.ConditionFn{
			func(bars []types.BarData, idx int) bool {
				if idx == 1 && !entrySignaled {
					entrySignaled = true
					return true
				}
				return false
			},
		},
		ExitLong: []types.ConditionFn{
			func(bars []types.BarData, idx int) bool {
				return idx == 5
			},
		},
		ATRStopMult: 10.0, // Wide stop so it doesn't trigger
	}

	eng := NewProbeEngine(strat, types.RiskMedium, newTestLogger())
	trades := eng.Run(bars)

	if len(trades) != 1 {
		t.Fatalf("expected 1 trade, got %d", len(trades))
	}

	if trades[0].ExitReason != "signal_exit" {
		t.Errorf("exit reason = %q, want signal_exit", trades[0].ExitReason)
	}
}

func TestTimeStopExit(t *testing.T) {
	bars := makeBars(30, 100, 0.1) // Slow uptrend, won't hit stops

	entrySignaled := false
	strat := &types.StrategyDef{
		ID:        1,
		Name:      "test",
		Direction: types.LongOnly,
		EntryLong: []types.ConditionFn{
			func(bars []types.BarData, idx int) bool {
				if idx == 1 && !entrySignaled {
					entrySignaled = true
					return true
				}
				return false
			},
		},
		TimeStopBars: 10,
	}

	eng := NewProbeEngine(strat, types.RiskMedium, newTestLogger())
	trades := eng.Run(bars)

	if len(trades) != 1 {
		t.Fatalf("expected 1 trade, got %d", len(trades))
	}

	if trades[0].ExitReason != "time_stop" {
		t.Errorf("exit reason = %q, want time_stop", trades[0].ExitReason)
	}
}

func TestDiscardOpenTradeAtEnd(t *testing.T) {
	// Entry signal on bar 1, enters on bar 2.
	// No exit conditions and no mechanical stops that trigger.
	// Bars end at 5 - trade should be discarded.
	bars := makeBars(5, 100, 0.1)

	strat := &types.StrategyDef{
		ID:        1,
		Name:      "test",
		Direction: types.LongOnly,
		EntryLong: []types.ConditionFn{
			func(bars []types.BarData, idx int) bool {
				return idx == 1
			},
		},
		// No exits configured
	}

	eng := NewProbeEngine(strat, types.RiskMedium, newTestLogger())
	trades := eng.Run(bars)

	if len(trades) != 0 {
		t.Errorf("expected 0 trades (open trade discarded), got %d", len(trades))
	}
}

func TestShortTrade(t *testing.T) {
	// Downward price series
	bars := makeBars(20, 110, -0.5)

	entrySignaled := false
	strat := &types.StrategyDef{
		ID:        1,
		Name:      "test",
		Direction: types.ShortOnly,
		EntryShort: []types.ConditionFn{
			func(bars []types.BarData, idx int) bool {
				if idx == 1 && !entrySignaled {
					entrySignaled = true
					return true
				}
				return false
			},
		},
		TimeStopBars: 8,
	}

	eng := NewProbeEngine(strat, types.RiskMedium, newTestLogger())
	trades := eng.Run(bars)

	if len(trades) != 1 {
		t.Fatalf("expected 1 trade, got %d", len(trades))
	}

	trade := trades[0]
	if trade.Direction != types.Short {
		t.Errorf("direction = %s, want short", trade.Direction)
	}

	// Price went down, so short should be profitable
	if trade.PnLPct <= 0 {
		t.Errorf("short trade in downtrend should be profitable, pnl = %f", trade.PnLPct)
	}
}

func TestMultipleTrades(t *testing.T) {
	bars := makeBars(50, 100, 0.1)

	callCount := 0
	strat := &types.StrategyDef{
		ID:        1,
		Name:      "test",
		Direction: types.LongOnly,
		EntryLong: []types.ConditionFn{
			func(bars []types.BarData, idx int) bool {
				// Signal on bars 1, 20, 35
				if idx == 1 || idx == 20 || idx == 35 {
					callCount++
					return true
				}
				return false
			},
		},
		TimeStopBars: 5,
	}

	eng := NewProbeEngine(strat, types.RiskMedium, newTestLogger())
	trades := eng.Run(bars)

	if len(trades) < 2 {
		t.Errorf("expected at least 2 trades, got %d", len(trades))
	}
}

func TestNoEntrySignals(t *testing.T) {
	bars := makeBars(20, 100, 0.5)

	strat := &types.StrategyDef{
		ID:        1,
		Name:      "test",
		Direction: types.LongOnly,
		EntryLong: []types.ConditionFn{
			func(bars []types.BarData, idx int) bool {
				return false // Never enters
			},
		},
	}

	eng := NewProbeEngine(strat, types.RiskMedium, newTestLogger())
	trades := eng.Run(bars)

	if len(trades) != 0 {
		t.Errorf("expected 0 trades, got %d", len(trades))
	}
}

func TestNoEntryConditions(t *testing.T) {
	bars := makeBars(20, 100, 0.5)

	strat := &types.StrategyDef{
		ID:        1,
		Name:      "test",
		Direction: types.LongOnly,
		// No entry conditions
	}

	eng := NewProbeEngine(strat, types.RiskMedium, newTestLogger())
	trades := eng.Run(bars)

	if len(trades) != 0 {
		t.Errorf("expected 0 trades with no entry conditions, got %d", len(trades))
	}
}

func TestPanicRecovery(t *testing.T) {
	bars := makeBars(20, 100, 0.5)

	strat := &types.StrategyDef{
		ID:        1,
		Name:      "test",
		Direction: types.LongOnly,
		EntryLong: []types.ConditionFn{
			func(bars []types.BarData, idx int) bool {
				if idx == 5 {
					panic("intentional test panic")
				}
				return false
			},
		},
	}

	eng := NewProbeEngine(strat, types.RiskMedium, newTestLogger())

	// Should not panic
	trades := eng.Run(bars)
	if len(trades) != 0 {
		t.Errorf("expected 0 trades, got %d", len(trades))
	}
}

func TestDirectionFiltering(t *testing.T) {
	bars := makeBars(20, 100, 0.5)

	entryLongCalled := false
	entryShortCalled := false
	strat := &types.StrategyDef{
		ID:        1,
		Name:      "test",
		Direction: types.LongOnly,
		EntryLong: []types.ConditionFn{
			func(bars []types.BarData, idx int) bool {
				if idx == 1 {
					entryLongCalled = true
				}
				return false
			},
		},
		EntryShort: []types.ConditionFn{
			func(bars []types.BarData, idx int) bool {
				if idx == 1 {
					entryShortCalled = true
				}
				return false
			},
		},
	}

	eng := NewProbeEngine(strat, types.RiskMedium, newTestLogger())
	eng.Run(bars)

	if !entryLongCalled {
		t.Error("entry long should be called for LongOnly strategy")
	}
	if entryShortCalled {
		t.Error("entry short should NOT be called for LongOnly strategy")
	}
}

func TestPnLCalculation(t *testing.T) {
	// Test that calcPnLPct works correctly
	// Long: (exit - entry) / entry
	pnl := calcPnLPct(100.0, 110.0, types.Long)
	if math.Abs(pnl-0.10) > 0.001 {
		t.Errorf("long PnL = %f, want 0.10", pnl)
	}

	// Short: (entry - exit) / entry
	pnl = calcPnLPct(100.0, 90.0, types.Short)
	if math.Abs(pnl-0.10) > 0.001 {
		t.Errorf("short PnL = %f, want 0.10", pnl)
	}

	// Long loss
	pnl = calcPnLPct(100.0, 95.0, types.Long)
	if math.Abs(pnl-(-0.05)) > 0.001 {
		t.Errorf("long loss PnL = %f, want -0.05", pnl)
	}
}

func TestTradeHasBarsHeld(t *testing.T) {
	bars := makeBars(30, 100, 0.1)

	entrySignaled := false
	strat := &types.StrategyDef{
		ID:        1,
		Name:      "test",
		Direction: types.LongOnly,
		EntryLong: []types.ConditionFn{
			func(bars []types.BarData, idx int) bool {
				if idx == 1 && !entrySignaled {
					entrySignaled = true
					return true
				}
				return false
			},
		},
		TimeStopBars: 10,
	}

	eng := NewProbeEngine(strat, types.RiskMedium, newTestLogger())
	trades := eng.Run(bars)

	if len(trades) != 1 {
		t.Fatalf("expected 1 trade, got %d", len(trades))
	}

	// Time stop after 10 bars (medium risk scale = 1.0)
	if trades[0].BarsHeld != 10 {
		t.Errorf("BarsHeld = %d, want 10", trades[0].BarsHeld)
	}
}

func TestTradeHasEntryExitTime(t *testing.T) {
	bars := makeBars(30, 100, 0.1)

	entrySignaled := false
	strat := &types.StrategyDef{
		ID:        1,
		Name:      "test",
		Direction: types.LongOnly,
		EntryLong: []types.ConditionFn{
			func(bars []types.BarData, idx int) bool {
				if idx == 1 && !entrySignaled {
					entrySignaled = true
					return true
				}
				return false
			},
		},
		TimeStopBars: 5,
	}

	eng := NewProbeEngine(strat, types.RiskMedium, newTestLogger())
	trades := eng.Run(bars)

	if len(trades) != 1 {
		t.Fatalf("expected 1 trade, got %d", len(trades))
	}

	trade := trades[0]
	// Entry time should be bar 2's timestamp
	if !trade.EntryTime.Equal(bars[2].Bar.Timestamp) {
		t.Errorf("entry time = %v, want %v", trade.EntryTime, bars[2].Bar.Timestamp)
	}
	// Exit time should be after entry time
	if !trade.ExitTime.After(trade.EntryTime) {
		t.Error("exit time should be after entry time")
	}
}
