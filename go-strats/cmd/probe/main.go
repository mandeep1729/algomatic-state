// Command probe runs strategy probes from the command line.
//
// Usage (CSV mode -- existing):
//
//	go run ./cmd/probe --strategy 1 --risk-profile medium --csv data.csv
//
// Usage (API mode -- new):
//
//	go run ./cmd/probe --strategy 1 --risk-profile medium \
//	    --api-url http://localhost:8000 --symbol AAPL --timeframe 1Hour \
//	    --start 2024-01-01 --end 2024-06-01
//
// Or use --all to run all 100 strategies.
package main

import (
	"context"
	"encoding/csv"
	"flag"
	"fmt"
	"log/slog"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/algomatic/strats100/go-strats/pkg/backend"
	"github.com/algomatic/strats100/go-strats/pkg/engine"
	"github.com/algomatic/strats100/go-strats/pkg/strategy"
	"github.com/algomatic/strats100/go-strats/pkg/types"
)

func main() {
	// Strategy selection flags
	strategyID := flag.Int("strategy", 0, "Strategy ID to run (1-100)")
	riskProfile := flag.String("risk-profile", "medium", "Risk profile: low, medium, high")
	runAll := flag.Bool("all", false, "Run all 100 strategies")
	listStrats := flag.Bool("list", false, "List all registered strategies")
	outputFile := flag.String("output", "", "Path for output CSV (default: stdout)")

	// Data source: CSV file (existing)
	csvFile := flag.String("csv", "", "Path to CSV file with OHLCV + indicators data")

	// Data source: Backend API (new)
	apiURL := flag.String("api-url", envOrDefault("BACKEND_API_URL", ""), "Python backend API base URL (e.g. http://localhost:8000)")
	symbol := flag.String("symbol", "", "Ticker symbol for API mode (e.g. AAPL)")
	timeframe := flag.String("timeframe", "", "Bar timeframe for API mode (e.g. 1Min, 15Min, 1Hour, 1Day)")
	startDate := flag.String("start", "", "Start date for API mode (ISO format, e.g. 2024-01-01)")
	endDate := flag.String("end", "", "End date for API mode (ISO format, e.g. 2024-06-01)")
	apiTimeout := flag.Duration("api-timeout", 30*time.Second, "Timeout per API request")

	flag.Parse()

	logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelInfo}))

	if *listStrats {
		listStrategies()
		return
	}

	if !*runAll && *strategyID == 0 {
		fmt.Fprintln(os.Stderr, "Error: must specify --strategy ID or --all")
		flag.Usage()
		os.Exit(1)
	}

	// Load data from CSV or API
	var bars []types.BarData
	var err error

	switch {
	case *csvFile != "" && *apiURL != "":
		fmt.Fprintln(os.Stderr, "Error: specify either --csv or --api-url, not both")
		os.Exit(1)

	case *csvFile != "":
		bars, err = loadCSV(*csvFile)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error loading CSV: %v\n", err)
			os.Exit(1)
		}
		logger.Info("Loaded bar data from CSV", "bars", len(bars), "file", *csvFile)

	case *apiURL != "":
		bars, err = loadFromAPI(logger, *apiURL, *symbol, *timeframe, *startDate, *endDate, *apiTimeout)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error loading data from API: %v\n", err)
			os.Exit(1)
		}
		logger.Info("Loaded bar data from API",
			"bars", len(bars), "symbol", *symbol,
			"timeframe", *timeframe, "api_url", *apiURL,
		)

	default:
		fmt.Fprintln(os.Stderr, "Error: must specify --csv or --api-url for data source")
		flag.Usage()
		os.Exit(1)
	}

	rp := types.RiskProfileByName(*riskProfile)

	// Determine which strategies to run
	var strategies []*types.StrategyDef
	if *runAll {
		strategies = strategy.GetAll()
	} else {
		s := strategy.Get(*strategyID)
		if s == nil {
			fmt.Fprintf(os.Stderr, "Error: strategy %d not found\n", *strategyID)
			os.Exit(1)
		}
		strategies = []*types.StrategyDef{s}
	}

	// Run strategies
	type result struct {
		strategyID   int
		strategyName string
		trades       []types.Trade
	}

	results := make([]result, len(strategies))
	var wg sync.WaitGroup
	start := time.Now()

	for i, strat := range strategies {
		wg.Add(1)
		go func(idx int, s *types.StrategyDef) {
			defer wg.Done()
			eng := engine.NewProbeEngine(s, rp, logger)
			trades := eng.Run(bars)
			results[idx] = result{
				strategyID:   s.ID,
				strategyName: s.Name,
				trades:       trades,
			}
		}(i, strat)
	}
	wg.Wait()

	elapsed := time.Since(start)
	totalTrades := 0
	for _, r := range results {
		totalTrades += len(r.trades)
	}
	logger.Info("Completed strategy run",
		"strategies", len(strategies),
		"total_trades", totalTrades,
		"elapsed", elapsed,
	)

	// Output results
	var w *csv.Writer
	if *outputFile != "" {
		f, err := os.Create(*outputFile)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error creating output file: %v\n", err)
			os.Exit(1)
		}
		defer f.Close()
		w = csv.NewWriter(f)
	} else {
		w = csv.NewWriter(os.Stdout)
	}
	defer w.Flush()

	// Write header
	w.Write([]string{
		"strategy_id", "strategy_name", "direction", "entry_time", "exit_time",
		"entry_price", "exit_price", "pnl_pct", "bars_held",
		"max_drawdown_pct", "max_profit_pct", "pnl_std", "exit_reason",
	})

	for _, r := range results {
		for _, t := range r.trades {
			w.Write([]string{
				strconv.Itoa(r.strategyID),
				r.strategyName,
				string(t.Direction),
				t.EntryTime.Format(time.RFC3339),
				t.ExitTime.Format(time.RFC3339),
				fmt.Sprintf("%.6f", t.EntryPrice),
				fmt.Sprintf("%.6f", t.ExitPrice),
				fmt.Sprintf("%.6f", t.PnLPct),
				strconv.Itoa(t.BarsHeld),
				fmt.Sprintf("%.6f", t.MaxDrawdownPct),
				fmt.Sprintf("%.6f", t.MaxProfitPct),
				fmt.Sprintf("%.6f", t.PnLStd),
				t.ExitReason,
			})
		}
	}
}

// loadFromAPI fetches bar data from the Python backend API.
func loadFromAPI(
	logger *slog.Logger,
	apiURL, symbol, timeframe, startDate, endDate string,
	timeout time.Duration,
) ([]types.BarData, error) {
	// Validate required API parameters
	if symbol == "" {
		return nil, fmt.Errorf("--symbol is required when using --api-url")
	}
	if timeframe == "" {
		return nil, fmt.Errorf("--timeframe is required when using --api-url")
	}
	if startDate == "" {
		return nil, fmt.Errorf("--start is required when using --api-url")
	}
	if endDate == "" {
		return nil, fmt.Errorf("--end is required when using --api-url")
	}

	start, err := parseTimestamp(startDate)
	if err != nil {
		return nil, fmt.Errorf("invalid --start: %w", err)
	}
	end, err := parseTimestamp(endDate)
	if err != nil {
		return nil, fmt.Errorf("invalid --end: %w", err)
	}

	client := backend.NewClient(apiURL, &backend.Config{
		Timeout:     timeout,
		Logger:      logger,
		EnableCache: true,
	})

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	barData, err := client.GetBarData(ctx, symbol, timeframe, start, end)
	if err != nil {
		return nil, fmt.Errorf("fetching bar data: %w", err)
	}

	if len(barData) == 0 {
		return nil, fmt.Errorf("no data returned from API for %s/%s (%s to %s)",
			symbol, timeframe, startDate, endDate)
	}

	return barData, nil
}

// envOrDefault returns the value of an environment variable,
// or the given default if the variable is unset or empty.
func envOrDefault(key, defaultVal string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultVal
}

func listStrategies() {
	strats := strategy.GetAll()
	fmt.Printf("%-4s %-45s %-16s %-12s\n", "ID", "Name", "Category", "Direction")
	fmt.Println(strings.Repeat("-", 80))
	for _, s := range strats {
		fmt.Printf("%-4d %-45s %-16s %-12s\n", s.ID, s.DisplayName, s.Category, s.Direction)
	}
	fmt.Printf("\nTotal: %d strategies\n", len(strats))
}

// loadCSV loads bar data from a CSV file.
// Expected columns: timestamp, open, high, low, close, volume, [indicator columns...]
func loadCSV(path string) ([]types.BarData, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("opening file: %w", err)
	}
	defer f.Close()

	reader := csv.NewReader(f)
	records, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("reading CSV: %w", err)
	}

	if len(records) < 2 {
		return nil, fmt.Errorf("CSV must have header + at least 1 data row")
	}

	headers := records[0]
	// Find column indices
	colIdx := make(map[string]int)
	for i, h := range headers {
		colIdx[strings.TrimSpace(strings.ToLower(h))] = i
	}

	// Required columns
	requiredCols := []string{"timestamp", "open", "high", "low", "close", "volume"}
	for _, col := range requiredCols {
		if _, ok := colIdx[col]; !ok {
			return nil, fmt.Errorf("missing required column: %s", col)
		}
	}

	bars := make([]types.BarData, 0, len(records)-1)
	for rowNum, row := range records[1:] {
		if len(row) != len(headers) {
			return nil, fmt.Errorf("row %d: expected %d columns, got %d", rowNum+2, len(headers), len(row))
		}

		// Parse timestamp
		ts, err := parseTimestamp(row[colIdx["timestamp"]])
		if err != nil {
			return nil, fmt.Errorf("row %d timestamp: %w", rowNum+2, err)
		}

		// Parse OHLCV
		open, _ := strconv.ParseFloat(row[colIdx["open"]], 64)
		high, _ := strconv.ParseFloat(row[colIdx["high"]], 64)
		low, _ := strconv.ParseFloat(row[colIdx["low"]], 64)
		closePrice, _ := strconv.ParseFloat(row[colIdx["close"]], 64)
		volume, _ := strconv.ParseFloat(row[colIdx["volume"]], 64)

		bar := types.Bar{
			Timestamp: ts,
			Open:      open,
			High:      high,
			Low:       low,
			Close:     closePrice,
			Volume:    volume,
		}

		// Parse indicator columns (everything else)
		indicators := make(types.IndicatorRow)
		for name, idx := range colIdx {
			if name == "timestamp" || name == "open" || name == "high" ||
				name == "low" || name == "close" || name == "volume" {
				continue
			}
			v, err := strconv.ParseFloat(row[idx], 64)
			if err == nil {
				indicators[name] = v
			}
		}

		bars = append(bars, types.BarData{Bar: bar, Indicators: indicators})
	}

	return bars, nil
}

// parseTimestamp tries multiple timestamp formats.
func parseTimestamp(s string) (time.Time, error) {
	formats := []string{
		time.RFC3339,
		"2006-01-02T15:04:05",
		"2006-01-02 15:04:05",
		"2006-01-02",
	}
	for _, f := range formats {
		t, err := time.Parse(f, s)
		if err == nil {
			return t, nil
		}
	}
	return time.Time{}, fmt.Errorf("unrecognized timestamp format: %s", s)
}
