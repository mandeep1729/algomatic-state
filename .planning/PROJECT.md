# Algomatic State

## What This Is

A data-driven momentum trading system using 1-minute stock data, enhanced by an AI-learned market "state" representation. The system combines hand-engineered features with deep learning to identify favorable trading regimes and execute momentum-based strategies via Alpaca API.

## Core Value

State representation improves baseline momentum strategy by identifying favorable market conditions — only trade when the market regime supports it.

## Requirements

### Validated

(None yet — ship to validate)

### Active

**Data Ingestion**
- [ ] Load 1-minute OHLCV data from local CSV files
- [ ] Fetch historical bars from Alpaca API with caching
- [ ] Validate data quality (gaps, outliers, schema)
- [ ] Support multiple asset symbols simultaneously

**Feature Engineering**
- [ ] Compute return features (log returns, momentum, ROC)
- [ ] Compute volatility features (realized vol, ATR, Garman-Klass)
- [ ] Compute volume features (volume ratios, OBV, VWAP)
- [ ] Compute market structure features (range, gaps, bar shape)
- [ ] Feature pipeline with caching and configurable sets

**State Representation**
- [ ] Create temporal windows of features
- [ ] Normalize features (z-score, robust scaling)
- [ ] Extract PCA-based state vectors (baseline)
- [ ] Train PyTorch autoencoder for nonlinear states
- [ ] Validate state quality via reconstruction metrics
- [ ] Cluster states into regimes

**Trading Strategy**
- [ ] Implement baseline momentum strategy
- [ ] Filter trades by favorable regimes
- [ ] Match current state to similar historical states
- [ ] Dynamic position sizing based on state confidence

**Backtesting**
- [ ] Event-driven backtesting engine
- [ ] Realistic execution simulation (slippage, commission)
- [ ] Walk-forward validation with rolling windows
- [ ] Performance metrics (Sharpe, Sortino, max DD)

**Live Execution**
- [ ] Connect to Alpaca paper trading API
- [ ] Submit and track orders
- [ ] Position reconciliation
- [ ] Risk controls (position limits, daily loss, drawdown circuit breaker)

### Out of Scope

- High-frequency trading (sub-second execution) — not designed for sub-second alpha
- Options or derivatives trading — US equities and ETFs only
- Fundamental analysis integration — pure technical/quantitative approach
- Social sentiment analysis — focusing on price/volume data only
- Mobile app — CLI and scripts only
- Real-time tick data — 1-minute bars sufficient for strategy

## Context

**Technical Environment:**
- Python 3.11+ with PyTorch for deep learning
- Alpaca Markets API for data and execution
- pandas/numpy for data processing, scikit-learn for PCA/clustering
- Target: $25k+ accounts (pattern day trader rule)

**Data:**
- 1-minute OHLCV bars only
- US equities and ETFs available on Alpaca
- Market hours only (9:30 AM - 4:00 PM ET)
- Local CSV files already available in data/ directory

**Existing Documentation:**
- PRD with detailed functional requirements (docs/PRD.md)
- Architecture design with layer structure (docs/ARCHITECTURE.md)
- User stories with acceptance criteria (docs/STORIES.md)

## Constraints

- **Testing**: Comprehensive test coverage for all functionality — unit tests for each component, integration tests for layer interactions
- **Modularity**: Small, single-responsibility components with clear interfaces — composition over inheritance, easy to swap implementations
- **Performance**: Feature computation < 100ms/1000 bars, state inference < 10ms, signal generation < 50ms
- **Reliability**: 99.5% uptime during market hours, graceful degradation on API failures
- **Security**: API keys in environment variables only, never in code or logs

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| PyTorch over TensorFlow | Flexibility for custom architectures, better debugging | — Pending |
| Conv1D autoencoder | Captures temporal patterns in feature windows | — Pending |
| Walk-forward validation | Prevents overfitting, simulates real trading conditions | — Pending |
| Alpaca API | Official SDK, supports paper and live trading, free tier available | — Pending |
| Layered architecture | Clear separation of concerns, testable components | — Pending |

---
*Last updated: 2025-01-19 after initialization*
