package aggregator

import (
	"testing"
	"time"

	"github.com/algomatic/marketdata-service/internal/db"
)

func makeBar(ts string, open, high, low, close float64, volume int64) db.OHLCVBar {
	t, err := time.Parse("2006-01-02T15:04", ts)
	if err != nil {
		panic(err)
	}
	return db.OHLCVBar{
		Timestamp: t,
		Open:      open,
		High:      high,
		Low:       low,
		Close:     close,
		Volume:    volume,
	}
}

func TestAggregate_5Min_Complete(t *testing.T) {
	// Five 1-minute bars forming one complete 5-minute bar.
	bars := []db.OHLCVBar{
		makeBar("2025-01-10T09:30", 100, 102, 99, 101, 1000),
		makeBar("2025-01-10T09:31", 101, 103, 100, 102, 1100),
		makeBar("2025-01-10T09:32", 102, 105, 101, 104, 1200),
		makeBar("2025-01-10T09:33", 104, 104, 98, 99, 900),
		makeBar("2025-01-10T09:34", 99, 101, 97, 100, 800),
		// Add bars for next complete period.
		makeBar("2025-01-10T09:35", 100, 106, 99, 105, 1500),
		makeBar("2025-01-10T09:36", 105, 107, 104, 106, 1600),
		makeBar("2025-01-10T09:37", 106, 108, 105, 107, 1700),
		makeBar("2025-01-10T09:38", 107, 109, 106, 108, 1800),
		makeBar("2025-01-10T09:39", 108, 110, 107, 109, 1900),
	}

	result, err := Aggregate(bars, "5Min")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(result) != 2 {
		t.Fatalf("expected 2 aggregated bars, got %d", len(result))
	}

	// First 5-min bar: 09:30-09:34.
	b := result[0]
	assertFloat(t, "open", 100, b.Open)
	assertFloat(t, "high", 105, b.High) // max(102,103,105,104,101)
	assertFloat(t, "low", 97, b.Low)    // min(99,100,101,98,97)
	assertFloat(t, "close", 100, b.Close)
	assertInt64(t, "volume", 5000, b.Volume) // 1000+1100+1200+900+800

	// Second 5-min bar: 09:35-09:39.
	b2 := result[1]
	assertFloat(t, "open", 100, b2.Open)
	assertFloat(t, "high", 110, b2.High)
	assertFloat(t, "low", 99, b2.Low)
	assertFloat(t, "close", 109, b2.Close)
	assertInt64(t, "volume", 8500, b2.Volume)
}

func TestAggregate_15Min(t *testing.T) {
	// Generate 15 bars for one complete 15-min period.
	var bars []db.OHLCVBar
	base, _ := time.Parse("2006-01-02T15:04", "2025-01-10T09:30")
	for i := 0; i < 15; i++ {
		ts := base.Add(time.Duration(i) * time.Minute)
		bars = append(bars, db.OHLCVBar{
			Timestamp: ts,
			Open:      float64(100 + i),
			High:      float64(110 + i),
			Low:       float64(90 + i),
			Close:     float64(105 + i),
			Volume:    int64(1000 + i*100),
		})
	}
	// Add one more bar to avoid dropping as incomplete.
	bars = append(bars, db.OHLCVBar{
		Timestamp: base.Add(15 * time.Minute),
		Open:      115, High: 125, Low: 105, Close: 120, Volume: 2500,
	})

	result, err := Aggregate(bars, "15Min")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(result) != 1 {
		t.Fatalf("expected 1 aggregated bar, got %d", len(result))
	}

	b := result[0]
	assertFloat(t, "open", 100, b.Open)    // First bar's open.
	assertFloat(t, "high", 124, b.High)    // Max high across 15 bars.
	assertFloat(t, "low", 90, b.Low)       // Min low across 15 bars.
	assertFloat(t, "close", 119, b.Close)  // Last bar's close.
	assertInt64(t, "volume", 25500, b.Volume) // Sum of volumes.
}

func TestAggregate_EmptyInput(t *testing.T) {
	result, err := Aggregate(nil, "5Min")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != nil {
		t.Fatalf("expected nil result for empty input, got %d bars", len(result))
	}
}

func TestAggregate_InvalidTimeframe(t *testing.T) {
	bars := []db.OHLCVBar{makeBar("2025-01-10T09:30", 100, 102, 99, 101, 1000)}
	_, err := Aggregate(bars, "2Min")
	if err == nil {
		t.Fatal("expected error for invalid timeframe")
	}
}

func TestAggregate_IncompletePeriodDropped(t *testing.T) {
	// Three 1-minute bars — not enough for a complete 5-minute bar.
	bars := []db.OHLCVBar{
		makeBar("2025-01-10T09:30", 100, 102, 99, 101, 1000),
		makeBar("2025-01-10T09:31", 101, 103, 100, 102, 1100),
		makeBar("2025-01-10T09:32", 102, 105, 101, 104, 1200),
	}

	result, err := Aggregate(bars, "5Min")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(result) != 0 {
		t.Fatalf("expected 0 bars (incomplete period dropped), got %d", len(result))
	}
}

func TestAggregate_1Hour(t *testing.T) {
	// Generate 60 bars for one complete hour.
	var bars []db.OHLCVBar
	base, _ := time.Parse("2006-01-02T15:04", "2025-01-10T10:00")
	for i := 0; i < 60; i++ {
		ts := base.Add(time.Duration(i) * time.Minute)
		bars = append(bars, db.OHLCVBar{
			Timestamp: ts,
			Open:      float64(100 + i),
			High:      float64(110 + i),
			Low:       float64(90),
			Close:     float64(105 + i),
			Volume:    100,
		})
	}
	// Add start of next hour to confirm completeness.
	bars = append(bars, db.OHLCVBar{
		Timestamp: base.Add(60 * time.Minute),
		Open:      160, High: 170, Low: 90, Close: 165, Volume: 100,
	})

	result, err := Aggregate(bars, "1Hour")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(result) != 1 {
		t.Fatalf("expected 1 aggregated bar, got %d", len(result))
	}

	b := result[0]
	assertFloat(t, "open", 100, b.Open)
	assertFloat(t, "close", 164, b.Close)
	assertFloat(t, "low", 90, b.Low)
	assertFloat(t, "high", 169, b.High) // 110 + 59
}

func assertFloat(t *testing.T, name string, expected, actual float64) {
	t.Helper()
	if expected != actual {
		t.Errorf("%s: expected %.2f, got %.2f", name, expected, actual)
	}
}

func assertInt64(t *testing.T, name string, expected, actual int64) {
	t.Helper()
	if expected != actual {
		t.Errorf("%s: expected %d, got %d", name, expected, actual)
	}
}
