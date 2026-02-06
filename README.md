# Algomatic State

Trading copilot platform combining HMM-based market regime tracking with a modular trade evaluation system (Trading Buddy) that surfaces risk, context, and inconsistencies to improve trading decisions.

## Overview

Algomatic State has two major subsystems:

1. **Regime Tracking Engine** -- Multi-timeframe Hidden Markov Model (HMM) approach to market state inference. The system learns continuous latent state vectors from engineered features and uses Gaussian HMMs to infer discrete market regimes.

2. **Trading Buddy (Trade Evaluation)** -- A modular evaluator orchestrator that reviews proposed trades against risk/reward checks, exit plan quality, regime fit, multi-timeframe alignment, and guardrails. Acts as a mentor and risk guardian, not a signal generator.

### Key Features

- **Multi-Timeframe Support**: Separate models for 1m, 5m, 15m, 1h, and 1d timeframes
- **HMM Regime Tracking**: Gaussian HMM with configurable state counts and covariance types
- **PCA Encoding**: Dimensionality reduction with automatic latent dimension selection
- **Anti-Chatter Controls**: Minimum dwell time, probability thresholds, majority voting
- **OOD Detection**: Log-likelihood based out-of-distribution detection
- **Walk-Forward Validation**: Time-based cross-validation with leakage prevention
- **Production Monitoring**: Drift detection, shadow inference, retraining triggers
- **Trade Evaluation**: Pluggable evaluator modules (risk/reward, exit plan, regime fit, MTFA)
- **Standalone Momentum Agent**: Dockerised agent with scheduler loop, risk manager, and Alpaca/Finnhub data providers
- **Broker Integration**: SnapTrade-based broker connection for trade history sync

## Architecture

```
Features x_t
     │
     ▼
Scaler (Robust/Standard/Yeo-Johnson)
     │
     ▼
Encoder (PCA or Temporal PCA)
     │
     ▼
Latent State z_t ∈ R^d
     │
     ▼
Gaussian HMM
     │
     ├─► Filtered Posterior α_t(k) = p(s_t=k | z_{1:t})
     │
     └─► Discrete Regime s_t ∈ {1..K}
```

## Installation

```bash
# Clone the repository
git clone https://github.com/mandeep1729/algomatic-state.git
cd algomatic-state

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

- `alpaca-py`: Alpaca Markets SDK for trading and market data
- `finnhub-python`: Finnhub market data provider
- `pandas`, `numpy`: Data manipulation
- `scikit-learn`: PCA and preprocessing
- `hmmlearn`: Gaussian HMM implementation
- `scipy`: Statistical transforms
- `pyarrow`: Parquet storage
- `pydantic`, `pydantic-settings`: Configuration management
- `SQLAlchemy`, `alembic`: Database ORM and migrations
- `FastAPI`, `uvicorn`: REST API backend
- `httpx`: Async HTTP client (agent scheduler)

## Quick Start

### 1. Initialize Database

```bash
python scripts/init_db.py
```

### 2. Download Market Data

```bash
python scripts/download_data.py --symbols AAPL MSFT --start 2023-01-01 --end 2024-01-01
```

### 3. Compute Features

```bash
python scripts/compute_features.py --symbols AAPL --timeframe 1Min
```

### 4. Train HMM Model

```python
from src.features.state.hmm import (
    TrainingPipeline,
    TrainingConfig,
    create_default_config,
)
import pandas as pd

# Load feature data
train_data = pd.read_parquet("data/features/train.parquet")
val_data = pd.read_parquet("data/features/val.parquet")

# Configure training
config = TrainingConfig(
    timeframe="1Min",
    symbols=["AAPL"],
    train_start=train_data.index.min(),
    train_end=train_data.index.max(),
    val_start=val_data.index.min(),
    val_end=val_data.index.max(),
    feature_names=["r5", "r15", "vol_z_60", "macd", "stoch_k"],
    n_states=8,
    latent_dim=6,
)

# Train model
pipeline = TrainingPipeline()
result = pipeline.train(config, train_data, val_data)

print(f"Model saved to: {result.paths.model_dir}")
print(f"Metrics: {result.metrics}")
```

### 5. Run Inference

```python
from src.features.state.hmm import InferenceEngine, get_model_path

# Load model
paths = get_model_path("1Min", "state_v001")
engine = InferenceEngine.from_artifacts(paths)

# Process new bar
features = {"r5": 0.01, "r15": 0.02, "vol_z_60": 1.5, "macd": 0.001, "stoch_k": 65.0}
output = engine.process(features, symbol="AAPL", timestamp=datetime.now())

print(f"State: {output.state_id}, Prob: {output.state_prob:.2f}")
print(f"Is OOD: {output.is_ood}")
```

### 6. Start the Web UI

The web UI provides interactive regime state visualization with price charts, feature exploration, and regime statistics. It consists of a FastAPI backend and a React frontend.

**Prerequisites:**
- Python virtual environment activated with dependencies installed
- Node.js 18+
- Database initialized (see step 1 above)
- `.env` file configured (copy from `.env.example` if not already done)

#### Option A: Using the startup script

```bash
# From the project root
./ui/start_ui.sh       # Linux/macOS
# or
cd ui && start_ui.bat  # Windows
```

This starts both the backend (port 8000) and frontend (port 5173) together.

#### Option B: Manual startup (two terminals)

**Terminal 1 -- Backend:**
```bash
# From the project root with venv activated
python -m ui.run_backend
```

The API server will be available at `http://localhost:8000` (docs at `http://localhost:8000/docs`).

**Terminal 2 -- Frontend:**
```bash
cd ui/frontend
npm install    # first time only
npm run dev
```

The UI will be available at `http://localhost:5173`.

See [docs/APIs.md](docs/APIs.md) for the full API reference.

### 7. Launch the Momentum Trading Agent

The momentum agent runs a configurable loop that fetches market data, computes features, generates momentum signals, and places paper trades via Alpaca. It includes an internal FastAPI endpoint for health checks and market data retrieval.

#### Option A: Docker Compose (recommended)

This starts PostgreSQL, builds the agent image, and runs the momentum agent container.

```bash
# 1. Copy and configure your environment
cp .env.example .env
# Edit .env to set ALPACA_API_KEY, ALPACA_SECRET_KEY, and optionally FINNHUB_API_KEY

# 2. Start the database
docker compose up -d

# 3. Start the momentum agent
docker compose -f docker-compose.agents.yml up -d momentum-agent

# 4. (Optional) Include pgAdmin for database management
docker compose --profile tools up -d

# 5. View agent logs
docker logs -f algomatic-momentum-agent
```

#### Option B: Run locally without Docker

```bash
# Ensure the database is running (either via Docker or locally)
docker compose up -d postgres

# Run the agent directly
python -m src.agent.main
```

#### Agent Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AGENT_SYMBOL` | `AAPL` | Ticker symbol to trade |
| `AGENT_INTERVAL_MINUTES` | `15` | Minutes between each loop iteration |
| `AGENT_DATA_PROVIDER` | `alpaca` | Market data source (`alpaca` or `finnhub`) |
| `AGENT_LOOKBACK_DAYS` | `5` | Days of historical data to fetch each cycle |
| `AGENT_POSITION_SIZE_DOLLARS` | `1` | Dollar amount per position (docker-compose uses `100`) |
| `AGENT_PAPER` | `true` | Use Alpaca paper trading (`true`/`false`) |
| `AGENT_LOG_LEVEL` | `INFO` | Agent logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `STRATEGY_MOMENTUM_FEATURE` | `r5` | Feature used for momentum signal |
| `STRATEGY_LONG_THRESHOLD` | `0.001` | Momentum value above which to go long |
| `STRATEGY_SHORT_THRESHOLD` | `-0.001` | Momentum value below which to go short |

The agent requires `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` to be set for order submission. If using Finnhub as the data provider, also set `FINNHUB_API_KEY`.

### 8. Launch Additional Trading Agents (Optional)

Besides the basic momentum agent, the project includes three additional trading strategy agents that can be run independently:

- **Breakout Agent**: Trades price breakouts above recent highs and breakdowns below recent lows
- **Contrarian Agent**: Takes positions against the prevailing momentum (mean reversion)
- **VWAP Agent**: Trades based on distance from Volume Weighted Average Price

#### Running Multiple Agents

Use the dedicated `docker-compose.agents.yml` file to run any combination of agents:

```bash
# Start infrastructure first
docker compose up -d postgres

# Start all agents
docker compose -f docker-compose.agents.yml up -d

# Or start specific agents
docker compose -f docker-compose.agents.yml up -d breakout-agent vwap-agent

# View logs for a specific agent
docker logs -f algomatic-breakout-agent
```

#### Agent-Specific Environment Variables

Each agent has its own environment variable prefix:

| Agent | Prefix | Key Feature | Default Thresholds |
|---|---|---|---|
| Momentum | `AGENT_` | `r5` (5-bar return) | long: 0.001, short: -0.001 |
| Contrarian | `CONTRARIAN_` | `r5` | long: -0.001, short: 0.001 |
| Breakout | `BREAKOUT_` | `breakout_20` (distance from 20-bar high) | long: 0.001, short: -0.02 |
| VWAP | `VWAP_` | `dist_vwap_60` (distance from VWAP) | long: 0.005, short: -0.005 |


## Project Structure

```
algomatic-state/
├── config/
│   ├── settings.py                 # Pydantic configuration (Settings, DatabaseConfig, etc.)
│   ├── assets.yaml                 # Asset universe
│   ├── features.json               # Feature configuration
│   ├── trading.yaml                # Trading strategy and backtest config
│   ├── state_vector_feature_spec.yaml  # HMM feature and model config
│   └── seed/                       # Database seed data (initial tickers, etc.)
│
├── src/
│   ├── agent/                      # Standalone trading agents
│   │   ├── main.py                # Momentum agent entry point (FastAPI + scheduler)
│   │   ├── config.py              # AgentConfig (env-based)
│   │   ├── strategy.py            # MomentumStrategy
│   │   ├── scheduler.py           # Async fetch-compute-trade loop
│   │   ├── api.py                 # Internal /market-data endpoint
│   │   ├── breakout_main.py       # Breakout agent entry point
│   │   ├── breakout_config.py     # Breakout agent configuration
│   │   ├── breakout_strategy.py   # Breakout trading strategy
│   │   ├── contrarian_main.py     # Contrarian agent entry point
│   │   ├── contrarian_config.py   # Contrarian agent configuration
│   │   ├── contrarian_strategy.py # Contrarian trading strategy
│   │   ├── vwap_main.py           # VWAP agent entry point
│   │   ├── vwap_config.py         # VWAP agent configuration
│   │   └── vwap_strategy.py       # VWAP trading strategy
│   │
│   ├── api/                        # Public API routers
│   │   ├── trading_buddy.py       # Trading Buddy REST endpoints
│   │   ├── broker.py              # SnapTrade broker integration
│   │   ├── auth.py                # Google OAuth authentication endpoints
│   │   ├── auth_middleware.py     # JWT token validation middleware
│   │   └── user_profile.py        # User profile and risk preference endpoints
│   │
│   ├── data/                       # Data loading and storage
│   │   ├── loaders/               # CSV, Alpaca, Database loaders
│   │   ├── database/              # SQLAlchemy models and repositories
│   │   ├── cache.py               # Data caching
│   │   ├── schemas.py             # Pandera OHLCV schema
│   │   └── quality.py             # Data quality checks
│   │
│   ├── marketdata/                 # Market data provider abstraction
│   │   ├── base.py                # MarketDataProvider ABC
│   │   ├── alpaca_provider.py     # Alpaca data provider
│   │   ├── finnhub_provider.py    # Finnhub data provider
│   │   └── utils.py               # Rate limiter, retry, normalisation
│   │
│   ├── features/                   # Feature engineering
│   │   ├── returns.py             # Return-based features
│   │   ├── volatility.py          # Volatility features
│   │   ├── volume.py              # Volume features
│   │   ├── intrabar.py            # Intrabar structure features
│   │   ├── anchor.py              # Anchor VWAP features
│   │   ├── time_of_day.py         # Time-of-day encoding
│   │   ├── market_context.py      # Market context features
│   │   ├── talib_indicators.py    # TA-Lib indicators
│   │   ├── pandas_ta_indicators.py # pandas-ta indicators
│   │   ├── pipeline.py            # Feature orchestration
│   │   ├── registry.py            # Feature registry
│   │   └── state/                 # State representation modules
│   │       ├── hmm/               # HMM regime tracking
│   │       │   ├── contracts.py   # Data contracts (FeatureVector, HMMOutput)
│   │       │   ├── config.py      # Configuration loading
│   │       │   ├── artifacts.py   # Model artifact management
│   │       │   ├── scalers.py     # Robust, Standard, Yeo-Johnson scalers
│   │       │   ├── encoders.py    # PCA and Temporal PCA encoders
│   │       │   ├── hmm_model.py   # Gaussian HMM wrapper
│   │       │   ├── data_pipeline.py # Feature loading, gap handling, splitting
│   │       │   ├── training.py    # Training pipeline
│   │       │   ├── inference.py   # Online inference engine
│   │       │   ├── storage.py     # Parquet state storage
│   │       │   ├── validation.py  # Model validation and diagnostics
│   │       │   └── monitoring.py  # Drift detection and operations
│   │       └── pca/               # PCA + K-means state computation
│   │           ├── contracts.py   # PCAStateOutput, PCAModelMetadata
│   │           ├── artifacts.py   # Model path management
│   │           ├── training.py    # PCAStateTrainer
│   │           ├── engine.py      # PCAStateEngine for inference
│   │           └── labeling.py    # Semantic state labeling
│   │
│   ├── trade/                      # Domain objects
│   │   ├── intent.py              # TradeIntent with validation
│   │   └── evaluation.py          # EvaluationResult, Severity, Evidence
│   │
│   ├── evaluators/                 # Trade evaluation engine
│   │   ├── base.py                # Evaluator ABC
│   │   ├── registry.py            # @register_evaluator decorator
│   │   ├── evidence.py            # Evidence helpers (z-scores, thresholds)
│   │   ├── context.py             # ContextPack and ContextPackBuilder
│   │   ├── risk_reward.py         # Risk/Reward evaluator
│   │   ├── exit_plan.py           # Exit plan evaluator
│   │   ├── regime_fit.py          # Regime fit evaluator
│   │   └── mtfa.py                # Multi-timeframe alignment evaluator
│   │
│   ├── orchestrator.py             # EvaluatorOrchestrator
│   ├── rules/
│   │   └── guardrails.py          # Output sanitisation (no-prediction policy)
│   │
│   ├── backtest/                   # Backtesting engine
│   │   ├── engine.py              # BacktestEngine
│   │   ├── walk_forward.py        # Walk-forward validation
│   │   ├── metrics.py             # Performance metrics
│   │   └── report.py              # Reporting
│   │
│   └── execution/                  # Live trading execution
│       ├── client.py              # Alpaca client wrapper
│       ├── orders.py              # Order types and status
│       ├── order_manager.py       # Order lifecycle
│       ├── order_tracker.py       # Order tracking
│       ├── risk_manager.py        # Risk checks
│       ├── runner.py              # Trading runner
│       └── snaptrade_client.py    # SnapTrade broker client
│
├── tests/                          # Test suite
│   └── unit/
│       ├── backtest/              # Backtest tests
│       ├── broker/                # Broker integration tests
│       ├── data/                  # Data layer tests
│       ├── evaluators/            # Evaluator tests
│       ├── execution/             # Execution tests
│       ├── features/              # Feature tests
│       └── hmm/                   # HMM module tests
│
├── models/                         # Trained model artifacts
│   └── ticker=AAPL/
│       └── timeframe=1Min/
│           └── model_id=state_v001/
│               ├── scaler.pkl
│               ├── encoder.pkl
│               ├── hmm.pkl
│               └── metadata.json
│
├── alembic/                        # Database migrations
│   └── versions/
│
├── ui/                             # Web UI
│   ├── backend/                   # FastAPI backend (api.py)
│   └── frontend/                  # React + TypeScript frontend
│
├── scripts/                        # CLI scripts
│   ├── helpers/                   # Shared helper modules
│   ├── download_data.py           # Download OHLCV data from Alpaca
│   ├── download_tickers.py        # Download and seed ticker metadata
│   ├── compute_features.py        # Compute technical features
│   ├── import_csv_to_db.py        # Import CSV/Parquet data to database
│   ├── init_db.py                 # Initialize database schema
│   ├── train_hmm.py               # Train HMM regime model
│   ├── analyze_hmm_states.py      # Analyze trained HMM states
│   ├── run_paper_trading.py       # Run paper trading session
│   └── run_live_trading.py        # Run live trading session
│
├── Dockerfile                      # Docker image for trading agents
├── docker-compose.yml              # PostgreSQL + pgAdmin services
├── docker-compose.agents.yml       # Trading agent services (momentum, breakout, etc.)
│
└── docs/                           # Documentation
    ├── ARCHITECTURE.md
    ├── APIs.md
    ├── DATABASE.md
    ├── FEATURE.md
    ├── PRD.md
    ├── PITFALLS.md
    ├── STATE_VECTOR_HMM_IMPLEMENTATION_PLAN.md
    ├── Trading_Buddy_Master_Roadmap_and_DB_Schema.md
    └── Trading_Buddy_Detailed_TODOs.md
```

## Configuration

### Feature Specification (config/state_vector_feature_spec.yaml)

```yaml
encoder_type: pca
scaler_type: robust
ood_threshold: -50.0

base_features:
  - r5
  - r15
  - r60
  - vol_z_60
  - macd
  - stoch_k
  # ... more features

timeframe_configs:
  1Min:
    n_states: 12
    latent_dim: 10
    min_dwell_bars: 5
    p_switch_threshold: 0.65

  1Hour:
    n_states: 6
    latent_dim: 6
    min_dwell_bars: 2
```

## HMM Module Components

### Data Contracts

- `FeatureVector`: Raw feature input with symbol, timestamp, and features dict
- `LatentStateVector`: Encoded latent representation
- `HMMOutput`: Inference output with state_id, probability, posterior, log-likelihood
- `ModelMetadata`: Model versioning and configuration

### Scalers

- `RobustScaler`: Median/IQR scaling (recommended for heavy tails)
- `StandardScaler`: Mean/std scaling
- `YeoJohnsonScaler`: Power transform for Gaussian alignment
- `CombinedScaler`: Per-feature configuration

### Encoders

- `PCAEncoder`: PCA-based dimensionality reduction
- `TemporalPCAEncoder`: Windowed temporal encoding

### Training

- `TrainingPipeline`: End-to-end training orchestrator
- `CrossValidator`: Walk-forward cross-validation
- `HyperparameterTuner`: Grid search for K, latent_dim, covariance type

### Inference

- `InferenceEngine`: Online inference with anti-chatter
- `MultiTimeframeInferenceEngine`: Coordinate multiple timeframes
- `RollingFeatureBuffer`: Maintain feature window state

### Validation

- `ModelValidator`: Complete validation pipeline
- `DwellTimeAnalyzer`: Regime duration statistics
- `TransitionAnalyzer`: Transition matrix diagnostics
- `WalkForwardBacktest`: Strategy comparison

### Monitoring

- `MetricsCollector`: Real-time monitoring metrics
- `DriftDetector`: PSI-based drift detection
- `ShadowInference`: Candidate model evaluation
- `RetrainingScheduler`: Automatic retraining triggers

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run HMM tests only
pytest tests/unit/hmm/ -v

# Run with coverage
pytest tests/unit/hmm/ --cov=src/features/state/hmm --cov-report=html
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md): System design and data flow
- [APIs](docs/APIs.md): REST API reference
- [Database](docs/DATABASE.md): Database schema, migrations, and configuration
- [Features](docs/FEATURE.md): Feature engineering specification
- [PRD](docs/PRD.md): Product requirements document
- [Pitfalls](docs/PITFALLS.md): ML and trading pitfalls research
- [HMM Implementation Plan](docs/STATE_VECTOR_HMM_IMPLEMENTATION_PLAN.md): Phase-by-phase HMM implementation
- [Trading Buddy Roadmap](docs/Trading_Buddy_Master_Roadmap_and_DB_Schema.md): Evaluation platform architecture
- [Trading Buddy TODOs](docs/Trading_Buddy_Detailed_TODOs.md): Detailed implementation status

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Make your changes following PEP 8 style
4. Write tests for new functionality
5. Commit with meaningful messages
6. Push and create a Pull Request
