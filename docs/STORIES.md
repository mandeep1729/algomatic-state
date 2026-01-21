# User Stories: Algomatic State

## Epic 1: Data Ingestion

### Story 1.1: Load Local CSV Data
**As a** quantitative researcher
**I want to** load OHLCV data from local CSV files
**So that** I can work with historical data I've already collected

**Acceptance Criteria:**
- [ ] Load CSV files with various date formats (MM/DD/YYYY HH:MM, ISO 8601)
- [ ] Automatically detect and parse timestamp column
- [ ] Validate OHLCV schema (open, high, low, close, volume)
- [ ] Handle missing values gracefully
- [ ] Return pandas DataFrame with datetime index

**Technical Notes:**
- Support existing oil_all.csv format
- Use pandera for schema validation

---

### Story 1.2: Fetch Alpaca Historical Data
**As a** quantitative researcher
**I want to** fetch historical bar data from Alpaca API
**So that** I can access a wide universe of US equities

**Acceptance Criteria:**
- [ ] Authenticate with Alpaca using API key/secret
- [ ] Fetch 1-minute bars for specified symbol and date range
- [ ] Handle pagination for large date ranges
- [ ] Implement rate limiting and retry logic
- [ ] Cache fetched data to avoid redundant API calls

**Technical Notes:**
- Use alpaca-py StockHistoricalDataClient
- Store cache in data/cache/ as parquet files

---

### Story 1.3: Load Multiple Assets
**As a** systematic trader
**I want to** load data for multiple assets at once
**So that** I can analyze and trade a basket of stocks

**Acceptance Criteria:**
- [ ] Load multiple symbols in a single call
- [ ] Return dictionary of DataFrames keyed by symbol
- [ ] Align timestamps across assets (handle missing bars)
- [ ] Parallelize loading for performance

---

### Story 1.4: Validate Data Quality
**As a** quantitative researcher
**I want to** automatically validate data quality
**So that** I can trust my analysis and catch data issues early

**Acceptance Criteria:**
- [ ] Check for required columns and correct dtypes
- [ ] Validate high >= max(open, close) and low <= min(open, close)
- [ ] Detect and flag gaps in timestamps
- [ ] Identify outliers (price spikes > 10%)
- [ ] Generate data quality report

---

## Epic 2: Feature Engineering

### Story 2.1: Compute Return Features
**As a** quantitative researcher
**I want to** compute various return-based features
**So that** I can capture price momentum at different timeframes

**Acceptance Criteria:**
- [ ] Log returns: r1, r5, r15, r60 (log(C_t / C_{t-n}))
- [ ] Cumulative return: cumret_60 (sum of r1 over 60 minutes)
- [ ] EMA difference: ema_diff = (EMA_12 - EMA_48) / close (normalized trend proxy)
- [ ] Trend slope: slope_60 (linear regression on log(close) over 60 minutes)
- [ ] Trend strength: trend_strength = |slope_60| / (rv_60 + eps)
- [ ] Handle lookback period correctly (NaN for insufficient data)

---

### Story 2.2: Compute Volatility Features
**As a** quantitative researcher
**I want to** compute volatility-based features
**So that** I can measure market risk and uncertainty

**Acceptance Criteria:**
- [ ] Realized volatility: rv_15, rv_60 (rolling std of r1)
- [ ] Normalized range: range_1 = (H - L) / (C + eps)
- [ ] ATR-like: atr_60 = mean(range_1) over 60 minutes
- [ ] Range z-score: range_z_60 = zscore(range_1; window=60)
- [ ] Volatility of volatility: vol_of_vol = std(rv_15) over 60 minutes

---

### Story 2.3: Compute Volume Features
**As a** quantitative researcher
**I want to** compute volume-based features
**So that** I can understand trading activity and liquidity

**Acceptance Criteria:**
- [ ] Raw volume: vol1 = V_t
- [ ] Dollar volume: dvol1 = C_t * V_t
- [ ] Relative volume: relvol_60 = V_t / (mean(V) over 60 minutes + eps)
- [ ] Volume z-score: vol_z_60 = zscore(V_t; window=60)
- [ ] Dollar volume z-score: dvol_z_60 = zscore(dvol1; window=60)

---

### Story 2.4: Compute Intrabar Structure Features
**As a** quantitative researcher
**I want to** compute features capturing bar structure and patterns
**So that** I can distinguish orderly trends from noisy reversals

**Acceptance Criteria:**
- [ ] Close location value: clv = (C - L) / (H - L + eps)
- [ ] Body ratio: body_ratio = |C - O| / (H - L + eps)
- [ ] Upper wick: upper_wick = (H - max(O, C)) / (H - L + eps)
- [ ] Lower wick: lower_wick = (min(O, C) - L) / (H - L + eps)

---

### Story 2.5: Compute Anchor & Location Features
**As a** quantitative researcher
**I want to** compute features capturing price location relative to key anchors
**So that** I can identify breakouts, pullbacks, and trend context

**Acceptance Criteria:**
- [ ] VWAP (60m): vwap_60 = sum(price * volume) / sum(volume) over 60 minutes
- [ ] Distance from VWAP: dist_vwap_60 = (C - vwap_60) / (C + eps)
- [ ] Distance from EMA: dist_ema_48 = (C - EMA_48) / (C + eps)
- [ ] Breakout level: breakout_20 = (C - rolling_high_20) / (C + eps)
- [ ] Pullback depth: pullback_depth = (rolling_high_20 - C) / (rolling_high_20 + eps)

---

### Story 2.6: Compute Time-of-Day Features
**As a** quantitative researcher
**I want to** encode time-of-day information in features
**So that** my state representation is explicitly time-aware

**Acceptance Criteria:**
- [ ] Time normalization: tod = minutes since market open (0 at 09:30)
- [ ] Cyclical encoding: tod_sin = sin(2π * tod / 390), tod_cos = cos(2π * tod / 390)
- [ ] Session flags: is_open_window (tod < 30), is_close_window (tod > 330)
- [ ] Optional: is_midday flag (120 <= tod <= 240)
- [ ] Optional: vol_z_by_tod, range_z_by_tod (z-score vs historical same minute)

---

### Story 2.7: Compute Market Context Features
**As a** quantitative researcher
**I want to** compute features relative to a market benchmark (e.g., SPY)
**So that** I can separate idiosyncratic moves from market-driven moves

**Acceptance Criteria:**
- [ ] Benchmark returns: mkt_r5, mkt_r15 (same formulas as asset returns)
- [ ] Benchmark volatility: mkt_rv_60
- [ ] Rolling beta: beta_60 = regression of asset r1 vs market r1 over 60 minutes
- [ ] Residual volatility: resid_rv_60 = std of regression residuals over 60 minutes
- [ ] Synchronized timestamps between asset and benchmark

**Technical Notes:**
- Requires loading benchmark data (SPY or QQQ) alongside asset data
- Beta and residual computations help filter regime detection

---

### Story 2.8: Configure Feature Sets
**As a** quantitative researcher
**I want to** define custom feature sets in configuration
**So that** I can easily experiment with different feature combinations

**Acceptance Criteria:**
- [ ] Define feature sets in YAML config
- [ ] Load features by name from registry
- [ ] Validate feature dependencies
- [ ] Support feature groups (all_returns, all_volatility, etc.)

---

### Story 2.9: Feature Pipeline Orchestration
**As a** quantitative researcher
**I want to** compute all features through a unified pipeline
**So that** I have a consistent and efficient feature computation process

**Acceptance Criteria:**
- [ ] Configure pipeline with list of features
- [ ] Compute features in optimal order
- [ ] Handle lookback periods (drop initial rows)
- [ ] Cache computed features for reuse
- [ ] Return clean DataFrame with no NaN values

---

## Epic 3: State Representation

### Story 3.1: Create Temporal Windows
**As a** quantitative researcher
**I want to** create sliding windows of features over time
**So that** I can capture short-term market context

**Acceptance Criteria:**
- [ ] Generate windows of configurable size (default 60 minutes)
- [ ] Support configurable stride (default 1)
- [ ] Output shape: (n_samples, window_size, n_features)
- [ ] Preserve timestamp alignment for each window

---

### Story 3.2: Normalize Features
**As a** quantitative researcher
**I want to** normalize features to avoid scale and regime biases
**So that** my state representation is robust across market conditions

**Acceptance Criteria:**
- [ ] Z-score normalization: (x - mean) / std
- [ ] Rolling normalization with configurable lookback
- [ ] Robust scaling option (median, IQR)
- [ ] Clip extreme values (default: 3 std)
- [ ] Fit on training data, transform on new data

---

### Story 3.3: Extract PCA State (Baseline)
**As a** quantitative researcher
**I want to** create a baseline state representation using PCA
**So that** I have a simple benchmark for comparison

**Acceptance Criteria:**
- [ ] Flatten windows: (samples, window*features)
- [ ] Fit PCA on training data
- [ ] Extract top k components (or % variance explained)
- [ ] Report explained variance per component
- [ ] Transform new data using fitted PCA

---

### Story 3.4: Train Autoencoder
**As a** quantitative researcher
**I want to** train a PyTorch autoencoder on temporal windows
**So that** I can learn a nonlinear state representation

**Acceptance Criteria:**
- [ ] Conv1D encoder with configurable architecture
- [ ] Bottleneck layer producing latent state
- [ ] Conv1D decoder reconstructing input
- [ ] Training loop with early stopping
- [ ] Learning rate scheduling
- [ ] Save/load trained models

---

### Story 3.5: Validate State Quality
**As a** quantitative researcher
**I want to** validate the quality of my learned state representation
**So that** I can ensure it captures meaningful market information

**Acceptance Criteria:**
- [ ] Reconstruction metrics (MSE, MAE, per-feature error)
- [ ] Cluster analysis (silhouette score, Calinski-Harabasz)
- [ ] Regime purity (return distribution per cluster)
- [ ] Temporal stability (state transition smoothness)
- [ ] Comparison: autoencoder vs PCA

---

### Story 3.6: Cluster States into Regimes
**As a** quantitative researcher
**I want to** cluster learned states into distinct regimes
**So that** I can identify favorable and unfavorable market conditions

**Acceptance Criteria:**
- [ ] K-means clustering with configurable k (default 5)
- [ ] Label regimes by historical performance
- [ ] Visualize regime characteristics (avg return, volatility)
- [ ] Analyze regime transition probabilities
- [ ] Support GMM as alternative clustering

---

## Epic 4: Trading Strategy

### Story 4.1: Implement Baseline Momentum Strategy
**As a** quantitative researcher
**I want to** implement a simple momentum strategy
**So that** I have a baseline to measure state enhancement against

**Acceptance Criteria:**
- [ ] Long when momentum > threshold
- [ ] Short when momentum < -threshold
- [ ] Flat otherwise
- [ ] Configurable parameters (window, threshold)
- [ ] Output standardized Signal objects

---

### Story 4.2: Filter Trades by Regime
**As a** systematic trader
**I want to** filter trades based on detected market regime
**So that** I only trade in favorable conditions

**Acceptance Criteria:**
- [ ] Classify current state into regime
- [ ] Look up historical regime performance
- [ ] Block trades in unfavorable regimes
- [ ] Configurable minimum regime score threshold
- [ ] Log regime decisions

---

### Story 4.3: Match Historical Patterns
**As a** systematic trader
**I want to** find similar historical market states
**So that** I can estimate expected outcomes for current conditions

**Acceptance Criteria:**
- [ ] Build nearest neighbor index on historical states
- [ ] Query k nearest states efficiently (FAISS/Annoy)
- [ ] Return historical outcomes following similar states
- [ ] Calculate expected return and confidence
- [ ] Use pattern match quality to filter/size trades

---

### Story 4.4: Dynamic Position Sizing
**As a** systematic trader
**I want to** dynamically size positions based on state confidence
**So that** I take larger positions when conditions are favorable

**Acceptance Criteria:**
- [ ] Base size determined by signal strength
- [ ] Scale by regime confidence
- [ ] Scale by pattern match quality
- [ ] Scale inversely by current volatility
- [ ] Respect maximum position limits

---

### Story 4.5: State-Enhanced Strategy Integration
**As a** systematic trader
**I want to** combine all state-based enhancements into one strategy
**So that** I have a complete trading system

**Acceptance Criteria:**
- [ ] Compose baseline strategy with regime filter
- [ ] Add pattern matching for additional confidence
- [ ] Apply dynamic position sizing
- [ ] Configurable enable/disable for each enhancement
- [ ] Log all enhancement decisions

---

## Epic 5: Backtesting

### Story 5.1: Build Backtesting Engine
**As a** quantitative researcher
**I want to** backtest strategies on historical data
**So that** I can evaluate performance before risking capital

**Acceptance Criteria:**
- [ ] Event-driven architecture (process bar by bar)
- [ ] Track positions and P&L
- [ ] Generate equity curve
- [ ] Support multiple assets
- [ ] Record all trades with timestamps

---

### Story 5.2: Simulate Realistic Execution
**As a** quantitative researcher
**I want to** simulate realistic execution costs
**So that** my backtest results are not overly optimistic

**Acceptance Criteria:**
- [ ] Configurable commission per share
- [ ] Configurable slippage in basis points
- [ ] Fill at next bar open (not current close)
- [ ] Option to simulate partial fills
- [ ] Track total costs separately

---

### Story 5.3: Calculate Performance Metrics
**As a** quantitative researcher
**I want to** calculate comprehensive performance metrics
**So that** I can evaluate strategy quality

**Acceptance Criteria:**
- [ ] Sharpe ratio (annualized)
- [ ] Sortino ratio
- [ ] Maximum drawdown (value and dates)
- [ ] Calmar ratio
- [ ] Win rate and profit factor
- [ ] Average trade duration

---

### Story 5.4: Walk-Forward Validation
**As a** quantitative researcher
**I want to** perform walk-forward validation
**So that** I can ensure my strategy is robust and not overfit

**Acceptance Criteria:**
- [ ] Configurable train/test window sizes
- [ ] Rolling window approach (step forward each period)
- [ ] Retrain models on each training window
- [ ] Evaluate on out-of-sample test window
- [ ] Aggregate results across all windows
- [ ] Report parameter stability

---

### Story 5.5: Generate Performance Reports
**As a** quantitative researcher
**I want to** generate visual performance reports
**So that** I can easily communicate and analyze results

**Acceptance Criteria:**
- [ ] Equity curve plot
- [ ] Drawdown plot
- [ ] Monthly returns heatmap
- [ ] Trade distribution analysis
- [ ] Regime performance breakdown
- [ ] Export to HTML/PDF

---

## Epic 6: Live Execution

### Story 6.1: Connect to Alpaca API
**As a** systematic trader
**I want to** connect to Alpaca trading API
**So that** I can execute trades programmatically

**Acceptance Criteria:**
- [ ] Authenticate with API key/secret
- [ ] Support paper and live endpoints
- [ ] Query account information
- [ ] Query current positions
- [ ] Handle connection errors gracefully

---

### Story 6.2: Submit Orders
**As a** systematic trader
**I want to** submit orders to Alpaca
**So that** I can execute my strategy's signals

**Acceptance Criteria:**
- [ ] Submit market orders
- [ ] Submit limit orders
- [ ] Specify quantity in shares or dollars
- [ ] Set time-in-force (day, GTC)
- [ ] Receive order confirmation

---

### Story 6.3: Track Order Status
**As a** systematic trader
**I want to** track order status and fills
**So that** I know the state of my orders

**Acceptance Criteria:**
- [ ] Poll order status
- [ ] Detect filled orders
- [ ] Handle partial fills
- [ ] Detect rejected orders
- [ ] Update internal position tracking

---

### Story 6.4: Implement Risk Controls
**As a** systematic trader
**I want to** enforce risk controls before trading
**So that** I protect my capital from excessive losses

**Acceptance Criteria:**
- [ ] Check position size limits
- [ ] Check daily loss limits
- [ ] Check maximum drawdown
- [ ] Reject orders that violate limits
- [ ] Alert when limits approached

---

### Story 6.5: Run Paper Trading
**As a** systematic trader
**I want to** run my strategy in paper trading mode
**So that** I can validate it with real market data

**Acceptance Criteria:**
- [ ] Connect to Alpaca paper trading
- [ ] Run strategy during market hours
- [ ] Process real-time data
- [ ] Execute paper trades
- [ ] Log all activity
- [ ] Generate daily summary

---

### Story 6.6: Run Live Trading
**As a** systematic trader
**I want to** run my strategy in live trading mode
**So that** I can generate real returns

**Acceptance Criteria:**
- [ ] Connect to Alpaca live trading
- [ ] Additional safety confirmations
- [ ] Real-time monitoring
- [ ] Emergency stop capability
- [ ] Position reconciliation
- [ ] Trade audit trail

---

## Epic 7: Configuration & Operations

### Story 7.1: Environment-Based Configuration
**As a** system operator
**I want to** configure the system via environment variables
**So that** I can manage different environments securely

**Acceptance Criteria:**
- [ ] API credentials from environment
- [ ] Environment type (dev, paper, production)
- [ ] Support .env files for development
- [ ] Never log credentials

---

### Story 7.2: YAML Configuration Files
**As a** quantitative researcher
**I want to** configure complex parameters via YAML
**So that** I can version control my configurations

**Acceptance Criteria:**
- [ ] Feature sets in config/trading.yaml
- [ ] Autoencoder architecture parameters
- [ ] Strategy parameters
- [ ] Asset universe in config/assets.yaml
- [ ] Validate configuration on load

---

### Story 7.3: Structured Logging
**As a** system operator
**I want to** have structured, searchable logs
**So that** I can debug issues and monitor system health

**Acceptance Criteria:**
- [ ] JSON-formatted log entries
- [ ] Include timestamp, level, module
- [ ] Include trade-specific context
- [ ] Configurable log level
- [ ] Rotate log files

---

### Story 7.4: CLI Scripts
**As a** quantitative researcher
**I want to** run common tasks via CLI scripts
**So that** I can easily execute workflows

**Acceptance Criteria:**
- [ ] scripts/download_data.py - Fetch historical data
- [ ] scripts/train_autoencoder.py - Train state model
- [ ] scripts/run_backtest.py - Run backtest
- [ ] scripts/run_paper_trading.py - Start paper trading
- [ ] Command-line arguments for parameters

---

## Story Priority Matrix

| Story | Priority | Complexity | Dependencies |
|-------|----------|------------|--------------|
| 1.1 Load CSV | P0 | Low | None |
| 1.2 Fetch Alpaca | P0 | Medium | 7.1 |
| 1.3 Multi-Asset | P1 | Medium | 1.1, 1.2 |
| 1.4 Validation | P0 | Low | 1.1 |
| 2.1 Returns | P0 | Low | 1.1 |
| 2.2 Volatility | P0 | Medium | 1.1 |
| 2.3 Volume | P0 | Medium | 1.1 |
| 2.4 Intrabar Structure | P0 | Low | 1.1 |
| 2.5 Anchor & Location | P0 | Low | 1.1, 2.2 |
| 2.6 Time-of-Day | P0 | Low | 1.1 |
| 2.7 Market Context | P1 | Medium | 1.3 |
| 2.8 Config Features | P1 | Low | 2.1-2.7 |
| 2.9 Pipeline | P0 | Medium | 2.1-2.7 |
| 3.1 Windows | P0 | Low | 2.9 |
| 3.2 Normalize | P0 | Medium | 3.1 |
| 3.3 PCA | P0 | Low | 3.2 |
| 3.4 Autoencoder | P0 | High | 3.2 |
| 3.5 Validate State | P0 | Medium | 3.3, 3.4 |
| 3.6 Regimes | P0 | Medium | 3.4 |
| 4.1 Momentum | P0 | Low | 2.9 |
| 4.2 Regime Filter | P0 | Medium | 3.6, 4.1 |
| 4.3 Pattern Match | P1 | High | 3.4 |
| 4.4 Position Size | P1 | Medium | 4.2 |
| 4.5 Integration | P0 | Medium | 4.1-4.4 |
| 5.1 Backtest | P0 | High | 4.5 |
| 5.2 Execution Sim | P0 | Medium | 5.1 |
| 5.3 Metrics | P0 | Medium | 5.1 |
| 5.4 Walk-Forward | P0 | High | 5.1, 3.4 |
| 5.5 Reports | P1 | Medium | 5.3 |
| 6.1 Alpaca Connect | P0 | Low | 7.1 |
| 6.2 Submit Orders | P0 | Medium | 6.1 |
| 6.3 Track Orders | P0 | Medium | 6.2 |
| 6.4 Risk Controls | P0 | Medium | 6.1 |
| 6.5 Paper Trading | P0 | High | 6.1-6.4, 4.5 |
| 6.6 Live Trading | P2 | High | 6.5 |
| 7.1 Env Config | P0 | Low | None |
| 7.2 YAML Config | P1 | Low | None |
| 7.3 Logging | P0 | Low | None |
| 7.4 CLI Scripts | P1 | Medium | All |

## Definition of Done

A story is considered done when:
1. All acceptance criteria are met
2. Unit tests are written and passing
3. Integration tests pass (where applicable)
4. Code is reviewed and merged
5. Documentation is updated
6. No known bugs remain
