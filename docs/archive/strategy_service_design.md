# Strategy Probe Execution Service -- Design Document

## 1. Executive Summary

The Python strategy probe system (`src/strats_prob/`) currently executes 100 TA-Lib
strategies across multiple symbols, timeframes, and risk profiles. The combinatorial
explosion (100 strategies x 3 timeframes x 3 risk profiles = 900 combinations per
symbol, each iterating bar-by-bar through thousands of OHLCV rows) makes the Python
implementation prohibitively slow for interactive or batch workflows.

This document specifies a standalone **Go** service that reimplements the probe engine
for high throughput while sharing the same PostgreSQL database, table schemas, and
semantic contract as the existing Python system.

---

## 2. Language Selection: Go

### Decision

**Go** is selected over C++ for the following reasons:

| Criterion | Go | C++ |
|---|---|---|
| Development velocity | High -- simple type system, fast compilation, rich stdlib | Low -- complex build systems, manual memory management |
| Concurrency | Goroutines + channels, trivial parallelism | Threads + mutexes, more boilerplate |
| REST API surface | `net/http` + `encoding/json` built-in | Requires external libraries (Crow, cpp-httplib) |
| TA-Lib binding | cgo wrapper around C TA-Lib (well-tested `markcheno/go-talib`) | Direct C linkage (slightly easier) |
| Cross-compilation | Single static binary per platform | Complex toolchain per target |
| Deployment | Tiny Docker image (scratch or alpine base) | Larger image, shared lib dependencies |
| Performance | Sufficient: tight loops compile to efficient machine code; goroutines give linear scaling across CPU cores | Marginally faster in tight loops, but the bottleneck is I/O and indicator computation, not loop overhead |

### Performance Justification

The Python bottleneck is:
1. **Interpreter overhead**: each bar-by-bar condition check is a Python function call.
2. **GIL**: no true parallelism across strategies.
3. **Pandas iloc**: high per-access overhead in the inner loop.

Go eliminates all three. The inner loop becomes a tight `for` over a `[]float64` slice
with zero allocation. Goroutines provide real parallelism. Expected speedup: 100-500x
over CPython, putting the 900-combination target well under 10 seconds for 10K bars per
timeframe.

### TA-Lib Binding

Use the `markcheno/go-talib` package which wraps the C TA-Lib library via cgo. This
provides all 70+ indicators used by the Python `TALibIndicatorCalculator`. For the Docker
image, the C TA-Lib library is compiled from source during the multi-stage build.

---

## 3. Architecture Overview

```
+-------------------+       +--------------------+       +------------------+
|  Python CLI /     |       |   Go Strategy      |       |   PostgreSQL     |
|  Orchestrator     | ----> |   Service          | <---> |   Database       |
|  (optional)       |  HTTP |                    |  SQL  |                  |
+-------------------+       +--------------------+       +------------------+
                                  |
                                  |  Reads: ohlcv_bars, computed_features,
                                  |         probe_strategies
                                  |  Writes: strategy_probe_results,
                                  |          strategy_probe_trades
```

The service runs as a standalone HTTP server (or CLI binary). It does NOT replace
the Python system -- the Python system remains the source of truth for strategy
*definitions* (the declarative `StrategyDef` dataclasses). The Go service loads
strategy *execution rules* from a JSON registry file that is auto-generated from
the Python definitions.

### Component Diagram

```
go-probe-service/
  cmd/
    probesvc/          # HTTP server entry point
      main.go
    probecli/          # CLI entry point (batch mode)
      main.go
  internal/
    config/            # YAML/env configuration
      config.go
    db/                # PostgreSQL connection + repository
      connection.go
      ohlcv_repo.go
      probe_repo.go
    engine/            # Core probe engine (bar-by-bar loop)
      engine.go
      engine_test.go
    exits/             # ExitManager (stop/target/trail/time)
      exits.go
      exits_test.go
    indicators/        # TA-Lib wrapper + caching
      calculator.go
      cache.go
    strategy/          # Strategy definition + registry
      definition.go
      registry.go
      condition.go     # Condition evaluators
    aggregator/        # Trade aggregation by dimensions
      aggregator.go
    api/               # HTTP handlers
      handlers.go
      middleware.go
    runner/            # Orchestrator (symbol x timeframe x strategy x risk)
      runner.go
  strategies.json      # Auto-generated from Python registry
  config.yaml          # Runtime configuration
  Dockerfile
  go.mod
  go.sum
```

---

## 4. Data Structures

### 4.1 Strategy Definition (JSON Registry)

Each strategy is serialized from the Python `StrategyDef` to JSON. The Go service
loads this at startup and compiles conditions into efficient evaluator functions.

```json
{
  "id": 1,
  "name": "ema20_ema50_trend_cross",
  "display_name": "EMA20/EMA50 Trend Cross",
  "philosophy": "Classic dual-EMA crossover captures medium-term trend shifts.",
  "category": "trend",
  "direction": "long_short",
  "tags": ["trend", "long_short", "cross", "signal", "atr_stop", "EMA", "ATR"],

  "entry_long": [
    {"type": "crosses_above", "col_a": "ema_20", "col_b": "ema_50"},
    {"type": "above", "col": "close", "ref": "ema_50"}
  ],
  "entry_short": [
    {"type": "crosses_below", "col_a": "ema_20", "col_b": "ema_50"},
    {"type": "below", "col": "close", "ref": "ema_50"}
  ],
  "exit_long": [
    {"type": "crosses_below", "col_a": "ema_20", "col_b": "ema_50"}
  ],
  "exit_short": [
    {"type": "crosses_above", "col_a": "ema_20", "col_b": "ema_50"}
  ],

  "atr_stop_mult": 2.0,
  "atr_target_mult": null,
  "trailing_atr_mult": 2.0,
  "time_stop_bars": null,

  "required_indicators": ["ema_20", "ema_50", "atr_14"]
}
```

### 4.2 Go Data Types

```go
// BarData represents a single OHLCV bar with pre-computed indicators.
// Stored as struct-of-arrays (columnar) for cache-friendly access.
type BarSeries struct {
    Timestamps []time.Time
    Open       []float64
    High       []float64
    Low        []float64
    Close      []float64
    Volume     []int64
    Indicators map[string][]float64  // e.g., "ema_20" -> [...]
}

// TradeResult mirrors Python ProbeTradeResult.
type TradeResult struct {
    EntryTime          time.Time
    ExitTime           time.Time
    EntryPrice         float64
    ExitPrice          float64
    Direction          string  // "long" or "short"
    PnlPct             float64
    BarsHeld           int
    MaxDrawdownPct     float64
    MaxProfitPct       float64
    PnlStd             float64
    ExitReason         string
    EntryJustification string
    ExitJustification  string
}

// RiskProfile mirrors Python RiskProfile.
type RiskProfile struct {
    Name        string
    StopScale   float64
    TargetScale float64
    TrailScale  float64
    TimeScale   float64
}

// Predefined risk profiles matching Python RISK_PROFILES.
var RiskProfiles = map[string]RiskProfile{
    "low":    {Name: "low",    StopScale: 0.75, TargetScale: 0.75, TrailScale: 0.75, TimeScale: 0.6},
    "medium": {Name: "medium", StopScale: 1.0,  TargetScale: 1.0,  TrailScale: 1.0,  TimeScale: 1.0},
    "high":   {Name: "high",   StopScale: 1.5,  TargetScale: 1.5,  TrailScale: 1.5,  TimeScale: 1.5},
}
```

### 4.3 Condition Evaluator System

The Python system uses closures (`ConditionFn = Callable[[DataFrame, int], bool]`).
The Go system uses a `Condition` interface with concrete implementations for each
condition type. The JSON `type` field maps to a Go struct:

```go
type Condition interface {
    Evaluate(series *BarSeries, idx int) bool
}

// CrossesAbove implements the Python crosses_above() condition.
type CrossesAbove struct {
    ColA string
    ColB string  // column name or empty if using a fixed value
    ValB float64 // used when ColB is empty
}

func (c *CrossesAbove) Evaluate(s *BarSeries, idx int) bool {
    if idx < 1 { return false }
    currA := s.Indicators[c.ColA][idx]
    prevA := s.Indicators[c.ColA][idx-1]
    currB := c.resolveB(s, idx)
    prevB := c.resolveB(s, idx-1)
    return prevA <= prevB && currA > currB
}
```

This approach:
- Avoids reflection or `interface{}` in the hot loop.
- Each condition type is a simple struct with direct field access.
- The JSON registry is parsed at startup into a slice of `Condition` interfaces.

Condition types to implement (matching `conditions.py`):

| Python factory | Go struct |
|---|---|
| `crosses_above` | `CrossesAbove` |
| `crosses_below` | `CrossesBelow` |
| `above` | `Above` |
| `below` | `Below` |
| `rising` | `Rising` |
| `falling` | `Falling` |
| `all_of` | `AllOf` |
| `any_of` | `AnyOf` |
| `pullback_to` | `PullbackTo` |
| `pullback_below` | `PullbackBelow` |
| `bullish_divergence` | `BullishDivergence` |
| `bearish_divergence` | `BearishDivergence` |
| `candle_bullish` | `CandleBullish` |
| `candle_bearish` | `CandleBearish` |
| `consecutive_higher_closes` | `ConsecutiveHigherCloses` |
| `consecutive_lower_closes` | `ConsecutiveLowerCloses` |
| `squeeze` | `Squeeze` |
| `range_exceeds_atr` | `RangeExceedsATR` |
| `narrowest_range` | `NarrowestRange` |
| `breaks_above_level` | `BreaksAboveLevel` |
| `breaks_below_level` | `BreaksBelowLevel` |
| `in_top_pct_of_range` | `InTopPctOfRange` |
| `in_bottom_pct_of_range` | `InBottomPctOfRange` |
| `gap_up` | `GapUp` |
| `gap_down` | `GapDown` |
| `deviation_from` | `DeviationFrom` |
| `was_below_then_crosses_above` | `WasBelowThenCrossesAbove` |
| `was_above_then_crosses_below` | `WasAboveThenCrossesBelow` |
| `held_for_n_bars` | `HeldForNBars` |

---

## 5. Core Engine Design

### 5.1 ProbeEngine

The engine mirrors the Python `ProbeEngine.run()` method exactly:

```
for each bar i in [0, N):
    1. If pending_signal and not in_position:
       - Fill at open[i], create ExitManager
       - Set position, skip to next bar
    2. If in_position:
       - Check signal exits (exit_long / exit_short conditions)
       - Check mechanical exits (stop/target/trail/time via ExitManager)
       - If exit triggered: record trade, reset to flat
    3. If flat and i < N-1:
       - Check entry_long conditions (if direction allows)
       - Check entry_short conditions (if direction allows)
       - Set pending_signal for next bar
    4. Discard open trades at end of data
```

Key semantics preserved from Python:
- **Fill-on-next-bar**: signal on bar i, entry at open of bar i+1.
- **Single open trade**: no pyramiding (MAX_CONCURRENT_TRADES = 1).
- **Open trades discarded**: positions still open at end of data are dropped.
- **ATR from `atr_14`**: required for all strategies.

### 5.2 ExitManager

Mirrors the Python `ExitManager` class exactly:

- **Risk profile scaling**: multipliers scaled by `{stop,target,trail,time}_scale`.
- **Tracking**: bars_held, best_price (MFE), worst_price (MAE), bar-by-bar P&L array.
- **Check order**: stop_loss -> target -> trailing_stop -> time_stop.
- **Trailing stop**: ratchets up (long) / down (short) as price extends.
- **Properties**: max_drawdown_pct, max_profit_pct, pnl_std (population std dev).

### 5.3 Indicator Computation

Indicators are computed ONCE per (symbol, timeframe) and cached in a `BarSeries.Indicators` map.

The Go service computes indicators using `markcheno/go-talib` which wraps the same
C TA-Lib library as the Python `talib` package. This ensures identical numerical
results.

Required indicators (union of all 100 strategies):

```
ema_20, ema_50, ema_200
sma_20, sma_50, sma_200
rsi_14, rsi_2
macd, macd_signal, macd_hist
bb_upper, bb_middle, bb_lower, bb_width
adx_14, plus_di_14, minus_di_14
atr_14
stoch_k, stoch_d
cci_20
willr_14
mfi_14
obv
adosc
sar
roc_10, mom_10
trix_15
apo_12_26
ppo, ppo_signal
aroon_up_25, aroon_down_25
kama_30
ht_trendline
linearreg_slope_20
cmo_14
stddev_20
max_high_10, max_high_20
min_low_10, min_low_20
```

Plus candlestick pattern columns:
```
cdl_engulfing, cdl_hammer, cdl_shooting_star, cdl_morning_star,
cdl_evening_star, cdl_doji, cdl_3whitesoldiers, cdl_3blackcrows,
cdl_harami, cdl_marubozu
```

### 5.4 Aggregator

Mirrors `aggregator.py`: groups trades by `(open_day, open_hour, long_short)` and
computes `num_trades`, `pnl_mean`, `pnl_std`, `max_drawdown`, `max_profit`.

---

## 6. API Specification

### 6.1 REST Endpoints

#### Health Check

```
GET /health
Response: 200 OK
{
  "status": "ok",
  "version": "1.0.0",
  "strategies_loaded": 100,
  "uptime_seconds": 3600
}
```

#### Submit Probe Run (Async)

```
POST /api/v1/runs
Content-Type: application/json

{
  "symbols": ["AAPL", "SPY"],
  "timeframes": ["15Min", "1Hour", "1Day"],
  "risk_profiles": ["low", "medium", "high"],
  "strategy_ids": null,
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "persist_trades": false,
  "run_id": null
}

Response: 202 Accepted
{
  "run_id": "a1b2c3d4",
  "status": "queued",
  "total_combinations": 2700,
  "estimated_seconds": 8
}
```

#### Get Run Status

```
GET /api/v1/runs/{run_id}

Response: 200 OK
{
  "run_id": "a1b2c3d4",
  "status": "running",
  "progress": {
    "completed": 1500,
    "total": 2700,
    "elapsed_seconds": 4.2
  }
}
```

```
GET /api/v1/runs/{run_id}   (after completion)

Response: 200 OK
{
  "run_id": "a1b2c3d4",
  "status": "completed",
  "summary": {
    "total_combinations": 2700,
    "total_trades": 12345,
    "total_result_records": 8901,
    "elapsed_seconds": 7.8
  }
}
```

#### Get Run Results

```
GET /api/v1/runs/{run_id}/results?symbol=AAPL&timeframe=1Hour&strategy_id=1

Response: 200 OK
{
  "results": [
    {
      "strategy_id": 1,
      "strategy_name": "ema20_ema50_trend_cross",
      "symbol": "AAPL",
      "timeframe": "1Hour",
      "risk_profile": "medium",
      "open_day": "2025-03-15",
      "open_hour": 10,
      "long_short": "long",
      "num_trades": 3,
      "pnl_mean": 0.0125,
      "pnl_std": 0.0045,
      "max_drawdown": 0.023,
      "max_profit": 0.041
    }
  ]
}
```

#### List Strategies

```
GET /api/v1/strategies?category=trend

Response: 200 OK
{
  "strategies": [
    {
      "id": 1,
      "name": "ema20_ema50_trend_cross",
      "display_name": "EMA20/EMA50 Trend Cross",
      "category": "trend",
      "direction": "long_short"
    }
  ]
}
```

### 6.2 Error Response Format

```json
{
  "error": {
    "code": "INVALID_SYMBOL",
    "message": "Symbol XYZ not found in database",
    "details": null
  }
}
```

Standard HTTP status codes: 400 (validation), 404 (not found), 500 (internal).

---

## 7. Database Schema Alignment

The Go service reads from and writes to the **same tables** as the Python system.
No schema changes are needed.

### Tables Read

| Table | Purpose |
|---|---|
| `tickers` | Look up ticker_id by symbol |
| `ohlcv_bars` | Load OHLCV bar data for a symbol + timeframe + date range |
| `computed_features` | Load pre-computed indicator values (JSONB) |
| `probe_strategies` | Look up strategy DB IDs by name |

### Tables Written

| Table | Purpose |
|---|---|
| `strategy_probe_results` | Aggregated results (upsert with ON CONFLICT DO NOTHING) |
| `strategy_probe_trades` | Individual trade records (bulk insert) |

### Key Queries

**Load bars:**
```sql
SELECT timestamp, open, high, low, close, volume
FROM ohlcv_bars
JOIN tickers ON tickers.id = ohlcv_bars.ticker_id
WHERE tickers.symbol = $1
  AND ohlcv_bars.timeframe = $2
  AND ohlcv_bars.timestamp >= $3
  AND ohlcv_bars.timestamp <= $4
ORDER BY ohlcv_bars.timestamp ASC;
```

**Load features:**
```sql
SELECT cf.bar_id, cf.features
FROM computed_features cf
JOIN ohlcv_bars ob ON ob.id = cf.bar_id
JOIN tickers t ON t.id = ob.ticker_id
WHERE t.symbol = $1
  AND ob.timeframe = $2
  AND ob.timestamp >= $3
  AND ob.timestamp <= $4
ORDER BY ob.timestamp ASC;
```

**Insert results:**
```sql
INSERT INTO strategy_probe_results (
  run_id, symbol, strategy_id, period_start, period_end,
  timeframe, risk_profile, open_day, open_hour, long_short,
  num_trades, pnl_mean, pnl_std, max_drawdown, max_profit
)
VALUES (...)
ON CONFLICT ON CONSTRAINT uq_probe_result_dimensions DO NOTHING;
```

**Insert trades:**
```sql
INSERT INTO strategy_probe_trades (
  strategy_probe_result_id, ticker, open_timestamp, close_timestamp,
  direction, open_justification, close_justification,
  pnl, pnl_pct, bars_held, max_drawdown, max_profit, pnl_std
)
VALUES (...);
```

### Resume / Idempotency

Before executing a strategy combination, the service queries:
```sql
SELECT COUNT(*) FROM strategy_probe_results
WHERE run_id = $1 AND strategy_id = $2 AND symbol = $3
  AND timeframe = $4 AND risk_profile = $5;
```
If count > 0, skip that combination (already processed in a previous partial run).

---

## 8. Parallelism Model

### 8.1 Data Loading (I/O bound)

- Load all OHLCV + features for a (symbol, timeframe) pair ONCE.
- Store in a `BarSeries` struct in memory.
- This is sequential per (symbol, timeframe) but can be prefetched with goroutines.

### 8.2 Strategy Execution (CPU bound)

For each (symbol, timeframe):
- A `BarSeries` is computed once with all indicators.
- Fan out 100 strategies x 3 risk profiles = 300 goroutines.
- Each goroutine runs its own `ProbeEngine.Run()` on the shared (read-only) `BarSeries`.
- Results are sent back via a buffered channel.
- A collector goroutine batches results and writes to DB.

```
                    +-- goroutine: engine.Run(strat=1, risk=low) --> channel
                    +-- goroutine: engine.Run(strat=1, risk=med) --> channel
 BarSeries(AAPL/1H) +-- goroutine: engine.Run(strat=1, risk=high) --> channel
                    +-- goroutine: engine.Run(strat=2, risk=low) --> channel
                    ...
                    +-- goroutine: engine.Run(strat=100, risk=high) --> channel
                                                                        |
                                                        collector goroutine
                                                        (batch DB writes)
```

### 8.3 Concurrency Limits

- Use a worker pool (`semaphore` pattern) to bound goroutines per CPU.
- Default: `runtime.NumCPU() * 2` concurrent strategy evaluations.
- DB writes use a separate connection pool (pgx pool with max 10 connections).

---

## 9. Configuration

### 9.1 config.yaml

```yaml
server:
  port: 8090
  read_timeout: 30s
  write_timeout: 300s
  shutdown_timeout: 10s

database:
  host: ${DB_HOST:localhost}
  port: ${DB_PORT:5432}
  name: ${DB_NAME:algomatic}
  user: ${DB_USER:algomatic}
  password: ${DB_PASSWORD:}
  ssl_mode: disable
  pool_max_conns: 20

engine:
  max_workers: 0  # 0 = NumCPU * 2
  db_batch_size: 500
  timeframes:
    - "15Min"
    - "1Hour"
    - "1Day"
  risk_profiles:
    - "low"
    - "medium"
    - "high"

strategies:
  registry_file: "strategies.json"

logging:
  level: "info"  # debug, info, warn, error
  format: "json"
```

### 9.2 Environment Variable Overrides

All config fields support `${ENV_VAR:default}` interpolation. Critical secrets
(DB password) should always come from environment variables, not the config file.

---

## 10. Deployment

### 10.1 Dockerfile (multi-stage)

```dockerfile
# Stage 1: Build TA-Lib C library
FROM golang:1.22-bookworm AS talib-builder
RUN apt-get update && apt-get install -y wget build-essential
RUN wget https://github.com/TA-Lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz \
    && tar xzf ta-lib-0.6.4-src.tar.gz \
    && cd ta-lib-0.6.4 \
    && ./configure --prefix=/usr/local \
    && make -j$(nproc) && make install

# Stage 2: Build Go binary
FROM talib-builder AS go-builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=1 go build -o /probe-service ./cmd/probesvc

# Stage 3: Runtime
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=talib-builder /usr/local/lib/libta_lib* /usr/local/lib/
RUN ldconfig
COPY --from=go-builder /probe-service /usr/local/bin/probe-service
COPY strategies.json /app/strategies.json
COPY config.yaml /app/config.yaml
WORKDIR /app
EXPOSE 8090
ENTRYPOINT ["probe-service"]
CMD ["--config", "/app/config.yaml"]
```

### 10.2 Docker Compose Integration

Add to the existing `docker-compose.yml`:

```yaml
services:
  probe-service:
    build:
      context: ./go-probe-service
      dockerfile: Dockerfile
    ports:
      - "8090:8090"
    environment:
      DB_HOST: db
      DB_PORT: 5432
      DB_NAME: algomatic
      DB_USER: algomatic
      DB_PASSWORD: ${DB_PASSWORD}
    depends_on:
      - db
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:8090/health"]
      interval: 10s
      timeout: 5s
      retries: 3
```

### 10.3 CLI Mode

For batch processing without the HTTP server:

```bash
probe-service run \
  --symbols AAPL,SPY \
  --timeframes 15Min,1Hour,1Day \
  --risk-profiles low,medium,high \
  --start 2025-01-01 \
  --end 2025-12-31 \
  --config /app/config.yaml
```

---

## 11. Strategy Registry Export (Python -> JSON)

A Python script generates `strategies.json` from the existing registry:

```python
# src/strats_prob/export_registry.py
import json
from src.strats_prob.registry import get_all_strategies

def export():
    """Export all strategy definitions to JSON for the Go service."""
    strategies = get_all_strategies()
    output = []
    for s in strategies:
        output.append({
            "id": s.id,
            "name": s.name,
            "display_name": s.display_name,
            "philosophy": s.philosophy,
            "category": s.category,
            "direction": s.direction,
            "tags": s.tags,
            "entry_long": _serialize_conditions(s.entry_long),
            "entry_short": _serialize_conditions(s.entry_short),
            "exit_long": _serialize_conditions(s.exit_long),
            "exit_short": _serialize_conditions(s.exit_short),
            "atr_stop_mult": s.atr_stop_mult,
            "atr_target_mult": s.atr_target_mult,
            "trailing_atr_mult": s.trailing_atr_mult,
            "time_stop_bars": s.time_stop_bars,
            "required_indicators": s.required_indicators,
        })
    return json.dumps(output, indent=2)
```

The condition serialization requires introspecting the closure state. Two approaches:

**A. Manual annotation**: Each strategy file also provides a `conditions_json` dict
alongside the `StrategyDef`. This is verbose but explicit and avoids reflection.

**B. Decorator-based**: Each condition factory (e.g., `crosses_above`) stores its
arguments in a `__condition_meta__` attribute, which the exporter reads. This is
cleaner but requires modifying `conditions.py`.

**Recommended**: Approach B. Add a `@serializable` decorator to each condition factory
that captures the arguments and attaches them to the returned closure. The exporter
reads `fn.__condition_meta__` to produce the JSON representation.

---

## 12. Performance Targets and Benchmarks

### Targets

| Metric | Target | Notes |
|---|---|---|
| Single symbol, 900 combos, 10K bars/tf | < 5 seconds | 3 timeframes x 100 strategies x 3 risk profiles |
| Single symbol, 900 combos, 50K bars/tf | < 20 seconds | Large date range |
| 10 symbols, 9000 combos, 10K bars/tf | < 30 seconds | Parallel across symbols |
| DB result write (batch 500) | < 200ms | Bulk INSERT with ON CONFLICT |
| API response (run submission) | < 100ms | Async job queuing |

### Benchmark Protocol

1. Load 10,000 1-Hour bars for AAPL from PostgreSQL.
2. Compute all indicators via go-talib.
3. Run all 100 strategies x 3 risk profiles (300 combinations).
4. Aggregate and write results to DB.
5. Report wall-clock time, peak memory, and per-strategy average time.

Compare against the Python system running the same workload on the same hardware.

---

## 13. Testing Strategy

### 13.1 Unit Tests

- **Engine**: verify trade entry/exit mechanics match Python output for known bar sequences.
- **ExitManager**: verify stop/target/trail/time logic with edge cases.
- **Conditions**: verify each condition type against reference data.
- **Aggregator**: verify grouping and stat computation.

### 13.2 Integration Tests

- **DB round-trip**: write results, read back, verify schema compatibility.
- **API**: HTTP handler tests with httptest.

### 13.3 Parity Tests

- Run both Python and Go engines on the same 1000-bar dataset for 10 strategies.
- Compare trade-by-trade output (entry time, exit time, direction, pnl_pct).
- Tolerate < 1e-8 float difference.
- This ensures the Go reimplementation is semantically identical to Python.

---

## 14. Migration Path

### Phase 1: Foundation (this design)
- Set up Go project skeleton.
- Implement BarSeries, ExitManager, and ProbeEngine.
- Implement 5 condition types (crosses_above, crosses_below, above, below, rising).
- Unit test against Python reference output.

### Phase 2: Full Condition Coverage
- Implement all 30 condition types from `conditions.py`.
- Implement JSON strategy registry loading.
- Run parity tests for all 100 strategies.

### Phase 3: DB Integration + API
- Implement PostgreSQL repositories (read OHLCV, write results).
- Implement HTTP API endpoints.
- Implement parallel runner with goroutine pool.

### Phase 4: Optimization + Deployment
- Profile and optimize hot paths.
- Build Docker image with TA-Lib.
- Add to docker-compose.
- Run performance benchmarks.
- Write Python client wrapper for calling the Go service from existing CLI.

### Phase 5: Deprecate Python Engine
- Once parity is confirmed and performance targets met, the Python `ProbeEngine`
  becomes a reference implementation used only for testing.
- The Python CLI (`cli.py`) gains a `--backend go` flag that delegates to the
  Go HTTP service instead of running locally.

---

## 15. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| go-talib numeric drift vs Python talib | Parity failures | Both use same C library; differences would be in float edge cases. Run parity tests on real data. |
| cgo overhead in indicator computation | Performance degradation | Compute indicators once per (symbol, timeframe), amortized over 300 strategy runs |
| Complex condition composition (all_of, any_of nesting) | Incorrect serialization | Parity tests on all 100 strategies; approach B decorator captures composition tree |
| DB connection exhaustion | Throughput bottleneck | Use pgx pool with bounded connections; batch writes (500 per INSERT) |
| Strategy definition drift (Python updated, JSON stale) | Wrong results | CI step: re-export JSON and fail if diff detected |

---

## 16. Open Questions

1. **Should the Go service compute indicators from raw OHLCV, or require pre-computed
   features in the DB?** Current design supports both: prefer DB features, fall back
   to computing via go-talib. This matches the Python runner's `_ensure_indicators()`.

2. **Should the Go service support the 1Min timeframe?** The task description says
   "15Min, 1Hour, 1Day ONLY" for the Go service. The Python system supports 1Min but
   it generates enormous data. Recommendation: exclude 1Min from Go service defaults
   but support it as a configuration option.

3. **gRPC vs REST?** REST is simpler and sufficient for the expected workload. gRPC
   can be added later if sub-millisecond internal RPC is needed.
