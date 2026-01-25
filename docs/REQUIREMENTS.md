# Algomatic State - Requirements Document

## Executive Summary

Algomatic State is a data-driven momentum trading system that uses an AI-learned market "state" representation to identify favorable trading regimes. The system combines hand-engineered technical features with deep learning to filter trades, match patterns, and size positions dynamically.

---

## 1. Data Management Requirements

### 1.1 Data Ingestion

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| DM-1.1 | Load 1-minute OHLCV data from local CSV/Parquet files | P0 | Done |
| DM-1.2 | Fetch historical bars from Alpaca API | P0 | Done |
| DM-1.3 | Support multiple timeframes: 1Min, 5Min, 15Min, 1Hour, 1Day | P0 | Done |
| DM-1.4 | Store data in PostgreSQL database for persistence | P0 | Done |
| DM-1.5 | Implement smart incremental data fetching (fetch only missing data) | P0 | Done |
| DM-1.6 | Auto-aggregate higher timeframes from 1Min source data | P0 | Done |
| DM-1.7 | Fetch 1Day data directly from Alpaca (not aggregated) | P1 | Done |
| DM-1.8 | Track data synchronization status per ticker/timeframe | P1 | Done |
| DM-1.9 | Handle timezone-aware timestamps consistently (UTC storage) | P0 | Done |

### 1.2 Data Validation

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| DV-1.1 | Validate OHLCV schema (high >= low, prices > 0, etc.) | P0 | Done |
| DV-1.2 | Detect and handle data gaps | P1 | Done |
| DV-1.3 | Unique constraint on (ticker, timeframe, timestamp) | P0 | Done |

---

## 2. Feature Engineering Requirements

### 2.1 Technical Indicators

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FE-2.1 | Compute comprehensive technical indicators using TA-Lib or pandas-ta | P0 | Done |
| FE-2.2 | Store computed features in JSONB format for flexibility | P0 | Done |
| FE-2.3 | Auto-compute indicators when new bar data is inserted | P0 | Done |
| FE-2.4 | Skip duplicate feature computation (check existing features first) | P0 | Done |
| FE-2.5 | Support manual trigger for feature computation via UI | P1 | Done |

### 2.2 Indicator Categories

**Momentum Indicators:**
- RSI (14-period)
- MACD (12/26/9)
- Stochastic (%K, %D)
- ADX (14-period)
- CCI (20-period)
- Williams %R (14-period)
- MFI (14-period)

**Trend Indicators:**
- SMA (20, 50, 200 periods)
- EMA (20, 50, 200 periods)
- Parabolic SAR
- Ichimoku Cloud (Tenkan, Kijun, Senkou A/B, Chikou)

**Volatility Indicators:**
- Bollinger Bands (upper, middle, lower, width, %B)
- ATR (14-period)

**Volume Indicators:**
- OBV (On-Balance Volume)
- VWAP (60-period rolling)

**Support/Resistance:**
- Pivot Points (PP, R1, R2, S1, S2)

### 2.3 Base Features for State Model

As specified in FEATURE.md:

| Category | Features |
|----------|----------|
| Returns & Trend | r1, r5, r15, r60, cumret_60, ema_diff, slope_60, trend_strength |
| Volatility & Range | rv_15, rv_60, range_1, atr_60, range_z_60, vol_of_vol |
| Volume | vol1, dvol1, relvol_60, vol_z_60, dvol_z_60 |
| Intrabar Structure | clv, body_ratio, upper_wick, lower_wick |
| Anchors & Location | vwap_60, dist_vwap_60, dist_ema_48, breakout_20, pullback_depth |
| Time-of-Day | tod_sin, tod_cos |

---

## 3. State Representation Requirements

### 3.1 Processing Pipeline

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| SR-3.1 | Create temporal windows of features (default: 60 minutes) | P0 | Done |
| SR-3.2 | Normalize features using z-score scaling | P0 | Done |
| SR-3.3 | Extract PCA-based state vectors (baseline method) | P0 | Done |
| SR-3.4 | Train PyTorch autoencoder for nonlinear state extraction | P0 | Partial |
| SR-3.5 | Cluster states into regimes using K-Means | P0 | Done |
| SR-3.6 | Validate state quality via reconstruction and clustering metrics | P1 | Done |

### 3.2 Regime Analysis

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| RA-3.1 | Calculate regime distribution (time spent in each regime) | P0 | Done |
| RA-3.2 | Calculate regime performance (Sharpe ratio per regime) | P0 | Done |
| RA-3.3 | Calculate regime transition probabilities | P0 | Done |
| RA-3.4 | Visualize regime states overlaid on price charts | P0 | Done |

---

## 4. Trading Strategy Requirements

### 4.1 Signal Generation

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| TS-4.1 | Implement baseline momentum strategy | P0 | Done |
| TS-4.2 | Filter trades by favorable regimes | P0 | Done |
| TS-4.3 | Match current state to similar historical states | P1 | Partial |
| TS-4.4 | Dynamic position sizing based on state confidence | P1 | Partial |

### 4.2 Risk Management

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| RM-4.1 | Position size limits (per-asset and portfolio) | P0 | Done |
| RM-4.2 | Daily loss limits | P0 | Done |
| RM-4.3 | Maximum drawdown circuit breaker | P0 | Done |
| RM-4.4 | Pre-trade risk checks | P0 | Done |

---

## 5. Backtesting Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| BT-5.1 | Event-driven backtesting engine | P0 | Done |
| BT-5.2 | Realistic execution simulation (slippage, commission) | P0 | Done |
| BT-5.3 | Walk-forward validation with rolling windows | P0 | Done |
| BT-5.4 | Calculate performance metrics (Sharpe, Sortino, max DD, etc.) | P0 | Done |
| BT-5.5 | Generate performance reports (JSON, Markdown) | P1 | Done |
| BT-5.6 | Monthly returns analysis | P1 | Done |

---

## 6. Execution Requirements

### 6.1 Alpaca Integration

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| EX-6.1 | Connect to Alpaca paper trading API | P0 | Done |
| EX-6.2 | Connect to Alpaca live trading API | P2 | Done |
| EX-6.3 | Submit market and limit orders | P0 | Done |
| EX-6.4 | Track order status and fills | P0 | Done |
| EX-6.5 | Position reconciliation | P1 | Partial |

---

## 7. User Interface Requirements

### 7.1 Visualization Dashboard

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| UI-7.1 | Display OHLCV candlestick charts with volume | P0 | Done |
| UI-7.2 | Use TradingView Lightweight Charts for performance | P1 | Done |
| UI-7.3 | Show regime states overlaid on price chart | P0 | Done |
| UI-7.4 | Display regime distribution (pie chart) | P1 | Done |
| UI-7.5 | Display regime performance (Sharpe by regime) | P1 | Done |
| UI-7.6 | Display transition matrix heatmap | P1 | Done |
| UI-7.7 | Time range slider with zoom controls | P0 | Done |

### 7.2 Data Controls

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| DC-7.1 | Ticker selection dropdown | P0 | Done |
| DC-7.2 | Timeframe selection (1Min, 5Min, 15Min, 1Hour, 1Day) | P0 | Done |
| DC-7.3 | Auto-load data when ticker/timeframe changes | P1 | Done |
| DC-7.4 | Show data availability indicator | P1 | Done |
| DC-7.5 | Button to manually trigger feature computation | P1 | Done |
| DC-7.6 | Clear cache functionality | P2 | Done |

### 7.3 Feature Exploration

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FX-7.1 | Toggle display of computed features | P1 | Done |
| FX-7.2 | Feature time series charts | P1 | Done |
| FX-7.3 | Feature statistics table | P2 | Done |

---

## 8. Database Requirements

### 8.1 Schema

| Table | Purpose |
|-------|---------|
| `tickers` | Symbol metadata (symbol, name, exchange, is_active) |
| `ohlcv_bars` | Price and volume data (OHLCV per ticker/timeframe/timestamp) |
| `computed_features` | Derived technical indicators (JSONB for flexibility) |
| `data_sync_log` | Track data synchronization status |

### 8.2 Technical Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| DB-8.1 | PostgreSQL 16 with Docker Compose | P0 | Done |
| DB-8.2 | Alembic migrations for schema changes | P0 | Done |
| DB-8.3 | Connection pooling (5 + 10 overflow) | P1 | Done |
| DB-8.4 | Bulk insert with upsert (ON CONFLICT DO NOTHING) | P1 | Done |
| DB-8.5 | Indexes for query performance | P1 | Done |
| DB-8.6 | Cascading deletes for data integrity | P1 | Done |

---

## 9. Configuration Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| CF-9.1 | Environment variables for credentials (Alpaca, DB) | P0 | Done |
| CF-9.2 | .env file support | P0 | Done |
| CF-9.3 | Pydantic settings for type-safe configuration | P1 | Done |
| CF-9.4 | YAML configuration for complex parameters | P1 | Done |

---

## 10. Non-Functional Requirements

### 10.1 Performance

| Metric | Target |
|--------|--------|
| Feature computation | < 100ms for 1000 bars |
| State inference | < 10ms per sample |
| Chart rendering | < 500ms for 7200 bars |
| API response time | < 2s for data loads |

### 10.2 Reliability

- System uptime: 99.5% during market hours
- Graceful degradation on API failures
- Automatic reconnection with exponential backoff
- State persistence for crash recovery

### 10.3 Maintainability

- Test coverage: >80% for core modules
- Type hints throughout codebase
- Modular architecture with clear interfaces
- Documentation for all public APIs

---

## 11. Implementation Decisions Made

### 11.1 Technical Choices

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Technical indicators library | pandas-ta (with TA-Lib fallback) | Pure Python, no system dependencies |
| Charting library | TradingView Lightweight Charts | Better performance than Plotly for OHLCV |
| Database | PostgreSQL with JSONB | Flexible feature storage, good indexing |
| Timeframe aggregation | From 1Min source | Ensures data consistency |
| Timestamp storage | UTC timezone-aware | Consistent across sources |

### 11.2 Design Patterns

| Pattern | Application |
|---------|-------------|
| Repository | Data access layer (OHLCVRepository) |
| Factory | Strategy creation (StrategyFactory) |
| Pipeline | Feature computation (FeaturePipeline) |
| Observer | Event-driven backtesting |

---

## 12. User Stories Completed

Based on development history:

1. **Data Loading**: "As a user, I can load OHLCV data from Alpaca or local files into the database"
2. **Auto-Aggregation**: "As a user, when I request data for a new symbol, the system fetches 1Min data and auto-aggregates to higher timeframes"
3. **Incremental Fetch**: "As a user, the system only fetches data I don't already have"
4. **Technical Indicators**: "As a user, I can view comprehensive technical indicators computed for my data"
5. **Auto-Compute Features**: "As a user, when new bar data is inserted, indicators are computed automatically"
6. **Skip Duplicates**: "As a user, the system doesn't recompute features that already exist"
7. **Manual Feature Trigger**: "As a user, I can click a button to compute features for a ticker"
8. **Regime Visualization**: "As a user, I can see market regime states overlaid on my price charts"
9. **Performance Analysis**: "As a user, I can see Sharpe ratios by regime to identify favorable conditions"

---

## 13. Known Issues & Technical Debt

| Issue | Impact | Status |
|-------|--------|--------|
| Ichimoku computation fails for 1Day (insufficient data) | Minor - other indicators work | Known |
| Test files were not tracked in git (gitignore pattern) | Fixed | Resolved |
| Timezone comparison in update_sync_log | Fixed | Resolved |

---

## 14. Future Enhancements

| Enhancement | Priority | Description |
|-------------|----------|-------------|
| Multi-task autoencoder training | P1 | Include momentum payoff prediction head |
| Pattern matching | P2 | kNN-based similar state lookup |
| Real-time updates | P2 | WebSocket for live data streaming |
| Alerting system | P2 | Notifications for regime changes |
| Mobile UI | P3 | Responsive design for mobile viewing |

---

## Appendix A: Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Walk-forward Sharpe Ratio | > 1.0 | TBD |
| Maximum Drawdown | < 15% | TBD |
| Win Rate | > 50% | TBD |
| State Enhancement Lift | > 20% | TBD |
| Test Coverage | > 80% | ~70% |

---

## Appendix B: Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12+ |
| Data Processing | pandas, numpy, pyarrow |
| Machine Learning | PyTorch, scikit-learn |
| Technical Indicators | pandas-ta, TA-Lib (optional) |
| Database | PostgreSQL 16, SQLAlchemy, Alembic |
| API Backend | FastAPI, uvicorn |
| API Client | Alpaca-py |
| UI Framework | React 18, TypeScript |
| Charting | TradingView Lightweight Charts, Plotly |
| Build Tool | Vite |
| Testing | pytest |
| Containerization | Docker Compose |
