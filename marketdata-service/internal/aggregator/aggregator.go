package aggregator

import (
	"fmt"
	"sort"
	"time"

	"github.com/algomatic/marketdata-service/internal/db"
)

// TimeframeDurations maps aggregatable timeframe names to their durations.
var TimeframeDurations = map[string]time.Duration{
	"5Min":  5 * time.Minute,
	"15Min": 15 * time.Minute,
	"1Hour": time.Hour,
}

// AggregatableTimeframes lists timeframes that can be derived from 1Min bars.
var AggregatableTimeframes = []string{"5Min", "15Min", "1Hour"}

// Aggregate groups 1Min bars into the target timeframe.
// The input bars must be sorted by timestamp ascending.
// Incomplete trailing periods are dropped.
func Aggregate(bars []db.OHLCVBar, targetTimeframe string) ([]db.OHLCVBar, error) {
	duration, ok := TimeframeDurations[targetTimeframe]
	if !ok {
		return nil, fmt.Errorf("unsupported aggregation timeframe: %q", targetTimeframe)
	}

	if len(bars) == 0 {
		return nil, nil
	}

	// Ensure sorted.
	sort.Slice(bars, func(i, j int) bool {
		return bars[i].Timestamp.Before(bars[j].Timestamp)
	})

	// Group bars by period boundary.
	groups := make(map[time.Time][]db.OHLCVBar)
	var keys []time.Time

	for _, bar := range bars {
		key := floorToInterval(bar.Timestamp, duration)
		if _, exists := groups[key]; !exists {
			keys = append(keys, key)
		}
		groups[key] = append(groups[key], bar)
	}

	// Sort period keys.
	sort.Slice(keys, func(i, j int) bool {
		return keys[i].Before(keys[j])
	})

	// Drop the last period if it might be incomplete.
	// A period is complete if the last bar is within the interval
	// and we have another period after it, or if it's not the trailing period.
	if len(keys) > 0 {
		lastKey := keys[len(keys)-1]
		periodEnd := lastKey.Add(duration)
		lastBar := bars[len(bars)-1]
		// If the last bar doesn't reach the period end, the period is incomplete.
		if lastBar.Timestamp.Before(periodEnd.Add(-1 * time.Minute)) {
			keys = keys[:len(keys)-1]
		}
	}

	// Aggregate each complete period.
	result := make([]db.OHLCVBar, 0, len(keys))
	for _, key := range keys {
		group := groups[key]
		if len(group) == 0 {
			continue
		}
		result = append(result, aggregateGroup(key, group))
	}

	return result, nil
}

// aggregateGroup builds one aggregated bar from a group of 1Min bars.
func aggregateGroup(periodStart time.Time, bars []db.OHLCVBar) db.OHLCVBar {
	first := bars[0]
	last := bars[len(bars)-1]

	high := first.High
	low := first.Low
	var totalVolume int64

	for _, b := range bars {
		if b.High > high {
			high = b.High
		}
		if b.Low < low {
			low = b.Low
		}
		totalVolume += b.Volume
	}

	return db.OHLCVBar{
		Timestamp: periodStart,
		Open:      first.Open,
		High:      high,
		Low:       low,
		Close:     last.Close,
		Volume:    totalVolume,
		Source:    "aggregated",
	}
}

// floorToInterval rounds a timestamp down to the nearest interval boundary.
func floorToInterval(t time.Time, d time.Duration) time.Time {
	// Use Unix epoch as reference point.
	truncated := t.Truncate(d)
	return truncated
}
