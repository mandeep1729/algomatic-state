// Package persistence provides trade aggregation and database persistence
// for strategy probe results. It mirrors the Python aggregation logic in
// src/strats_prob/aggregator.py and persistence in src/strats_prob/runner.py.
package persistence

import (
	"math"
	"strings"
	"time"

	"github.com/algomatic/strats100/go-strats/pkg/types"
)

// GroupKey identifies a unique aggregation group matching the Python dimensions:
// (open_day=date, open_hour=0-23, long_short="long"|"short").
type GroupKey struct {
	OpenDay   time.Time // Calendar date only (YYYY-MM-DD), time part is zero
	OpenHour  int       // 0-23
	LongShort string    // "long" or "short"
}

// AggregatedResult holds the computed statistics for one group of trades.
// Maps directly to a row in the strategy_probe_results table.
type AggregatedResult struct {
	// Identification
	RunID       string
	Symbol      string
	StrategyID  int
	PeriodStart time.Time
	PeriodEnd   time.Time

	// Dimensions
	Timeframe   string
	RiskProfile string
	OpenDay     time.Time // Calendar date (YYYY-MM-DD)
	OpenHour    int
	LongShort   string

	// Aggregations
	NumTrades   int
	PnLMean     float64
	PnLStd      float64
	MaxDrawdown float64
	MaxProfit   float64
}

// TradeRecord holds the fields for one row in the strategy_probe_trades table.
type TradeRecord struct {
	ResultID           int64 // FK to strategy_probe_results.id (set after result insert)
	Ticker             string
	OpenTimestamp      time.Time
	CloseTimestamp     time.Time
	Direction          string
	OpenJustification  string
	CloseJustification string
	PnL                float64 // Currency P&L = pnl_pct * entry_price
	PnLPct             float64
	BarsHeld           int
	MaxDrawdown        float64
	MaxProfit          float64
	PnLStd             float64
}

// AggregateTrades groups trades by (open_day, open_hour, long_short) and
// computes per-group statistics. This matches the Python aggregate_trades()
// function in src/strats_prob/aggregator.py.
func AggregateTrades(
	trades []types.Trade,
	strategyID int,
	symbol, timeframe, riskProfile, runID string,
	periodStart, periodEnd time.Time,
) []AggregatedResult {
	if len(trades) == 0 {
		return nil
	}

	// Group trades by dimensions
	groups := make(map[GroupKey][]types.Trade)
	for _, t := range trades {
		key := GroupKey{
			OpenDay:   truncateToDate(t.EntryTime),
			OpenHour:  t.EntryTime.Hour(),
			LongShort: normalizeDirection(string(t.Direction)),
		}
		groups[key] = append(groups[key], t)
	}

	// Compute aggregations per group
	results := make([]AggregatedResult, 0, len(groups))
	for key, groupTrades := range groups {
		pnls := make([]float64, len(groupTrades))
		var maxDD, maxProfit float64

		for i, t := range groupTrades {
			pnls[i] = t.PnLPct
			if t.MaxDrawdownPct > maxDD {
				maxDD = t.MaxDrawdownPct
			}
			if t.MaxProfitPct > maxProfit {
				maxProfit = t.MaxProfitPct
			}
		}

		results = append(results, AggregatedResult{
			RunID:       runID,
			Symbol:      strings.ToUpper(symbol),
			StrategyID:  strategyID,
			PeriodStart: periodStart,
			PeriodEnd:   periodEnd,
			Timeframe:   timeframe,
			RiskProfile: riskProfile,
			OpenDay:     key.OpenDay,
			OpenHour:    key.OpenHour,
			LongShort:   key.LongShort,
			NumTrades:   len(groupTrades),
			PnLMean:     mean(pnls),
			PnLStd:      stddev(pnls),
			MaxDrawdown: maxDD,
			MaxProfit:   maxProfit,
		})
	}

	return results
}

// BuildTradeRecords converts engine trades to TradeRecord structs ready for
// DB insertion. The ResultID field is left as 0 and must be set after the
// corresponding AggregatedResult is inserted and its DB ID is known.
func BuildTradeRecords(trades []types.Trade, symbol string) []TradeRecord {
	records := make([]TradeRecord, len(trades))
	for i, t := range trades {
		records[i] = TradeRecord{
			Ticker:             strings.ToUpper(symbol),
			OpenTimestamp:      t.EntryTime,
			CloseTimestamp:     t.ExitTime,
			Direction:          normalizeDirection(string(t.Direction)),
			OpenJustification:  t.EntryJustification,
			CloseJustification: t.ExitJustification,
			PnL:                t.PnLPct * t.EntryPrice,
			PnLPct:             t.PnLPct,
			BarsHeld:           t.BarsHeld,
			MaxDrawdown:        t.MaxDrawdownPct,
			MaxProfit:          t.MaxProfitPct,
			PnLStd:             t.PnLStd,
		}
	}
	return records
}

// MapTradesToResults assigns each TradeRecord a ResultID by looking up its
// group key in the provided map. Trades that don't match any result are
// skipped (returned in the second slice).
func MapTradesToResults(
	tradeRecords []TradeRecord,
	trades []types.Trade,
	resultIDMap map[GroupKey]int64,
) (matched []TradeRecord, unmatched int) {
	matched = make([]TradeRecord, 0, len(tradeRecords))
	for i, tr := range tradeRecords {
		key := GroupKey{
			OpenDay:   truncateToDate(trades[i].EntryTime),
			OpenHour:  trades[i].EntryTime.Hour(),
			LongShort: tr.Direction,
		}
		if rid, ok := resultIDMap[key]; ok {
			tr.ResultID = rid
			matched = append(matched, tr)
		} else {
			unmatched++
		}
	}
	return matched, unmatched
}

// truncateToDate strips the time component, returning midnight UTC of that date.
func truncateToDate(t time.Time) time.Time {
	y, m, d := t.Date()
	return time.Date(y, m, d, 0, 0, 0, 0, time.UTC)
}

// normalizeDirection ensures the direction string is "long" or "short"
// (truncated to 5 chars to match Python's direction[:5]).
func normalizeDirection(d string) string {
	if len(d) > 5 {
		return d[:5]
	}
	return d
}

// mean computes the arithmetic mean of a float64 slice.
func mean(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	sum := 0.0
	for _, v := range values {
		sum += v
	}
	return sum / float64(len(values))
}

// stddev computes the population standard deviation of a float64 slice.
// Returns 0 if fewer than 2 values (matching Python np.std with ddof=0,
// but returning 0 for single-element slices as in the aggregator).
func stddev(values []float64) float64 {
	n := len(values)
	if n <= 1 {
		return 0
	}
	m := mean(values)
	sumSq := 0.0
	for _, v := range values {
		d := v - m
		sumSq += d * d
	}
	return math.Sqrt(sumSq / float64(n))
}
