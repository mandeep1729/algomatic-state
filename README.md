# Algomatic State

Trading copilot platform combining HMM-based market regime tracking with a modular trade evaluation system (Trading Buddy) that surfaces risk, context, and inconsistencies to improve trading decisions.

## Overview

Algomatic State has three major subsystems:

1. **Regime Tracking Engine** -- Multi-timeframe Hidden Markov Model (HMM) approach to market state inference. The system learns continuous latent state vectors from engineered features and uses Gaussian HMMs to infer discrete market regimes.

2. **Trading Buddy (Trade Evaluation)** -- A modular evaluator orchestrator that reviews proposed trades against risk/reward checks, exit plan quality, regime fit, multi-timeframe alignment, and guardrails. Acts as a mentor and risk guardian, not a signal generator.

3. **Messaging & Market Data Service** -- An in-memory pub/sub message bus (`src/messaging/`) decouples market data fetching from consumers. A centralized `MarketDataService` handles gap detection, provider fetching, and DB persistence. The `MarketDataOrchestrator` wires the two together so that any component can request fresh data by publishing a `MARKET_DATA_REQUEST` event.

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
- **Broker Integration**: SnapTrade-based broker connection and direct Alpaca API for trade history sync

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
# From the project root (Linux/macOS)
./ui/start_ui.sh
```

```cmd
:: From the project root (Windows)
cd ui && start_ui.bat
```

This starts both the backend (port 8729 by default) and frontend (port 5173) together.

#### Option B: Manual startup (two terminals)

**Terminal 1 -- Backend:**
```bash
# From the project root with venv activated
python -m ui.run_backend

# Alternative: run uvicorn directly (use SERVER_PORT from .env or default 8729)
python -m uvicorn ui.backend.api:app --host 0.0.0.0 --port 8729 --reload
```

The API server will be available at `http://localhost:8729` (docs at `http://localhost:8729/docs`).

> **Note:** The backend port is configurable via `SERVER_PORT` in `.env` (default: 8729).

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

#### Option A: Using the startup script (recommended)

The `start-agents.sh` script handles log directory creation with proper permissions and starts agents via Docker Compose:

```bash
# 1. Copy and configure your environment
cp .env.example .env
# Edit .env to set ALPACA_API_KEY, ALPACA_SECRET_KEY, and optionally FINNHUB_API_KEY

# 2. Start the database first
docker compose up -d postgres

# 3. Start all agents in the background
./start-agents.sh -d

# Or start a specific agent
./start-agents.sh -d momentum-agent

# View agent logs
docker logs -f trader-momentum-agent
```

#### Option B: Docker Compose (manual)

If you prefer to run Docker Compose directly without the helper script:

```bash
# 1. Copy and configure your environment
cp .env.example .env
# Edit .env to set ALPACA_API_KEY, ALPACA_SECRET_KEY, and optionally FINNHUB_API_KEY

# 2. Start the database
docker compose up -d postgres

# 3. Start the momentum agent
docker compose -f docker-compose.agents.yml up -d momentum-agent

# 4. (Optional) Include pgAdmin for database management
docker compose --profile tools up -d

# 5. View agent logs
docker logs -f trader-momentum-agent
```

#### Option C: Run locally without Docker

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
| `AGENT_POSITION_SIZE_DOLLARS` | `1` | Dollar amount per position (docker-compose uses `1000`) |
| `AGENT_PAPER` | `true` | Use Alpaca paper trading (`true`/`false`) |
| `AGENT_API_PORT` | `8000` | Port for internal FastAPI health/data endpoint |
| `AGENT_LOG_LEVEL` | `INFO` | Agent logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `STRATEGY_MOMENTUM_FEATURE` | `r5` | Feature used for momentum signal |
| `STRATEGY_LONG_THRESHOLD` | `0.001` | Momentum value above which to go long |
| `STRATEGY_SHORT_THRESHOLD` | `-0.001` | Momentum value below which to go short |

The agent requires `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` to be set for order submission. If using Finnhub as the data provider, also set `FINNHUB_API_KEY`.

#### Log Locations

Logs are written to the following locations:

| Running Mode | Log Location |
|---|---|
| Docker (via `start-agents.sh`) | `~/projects/algomatic/logs/momentum-agent-logs/` |
| Docker (manual) | Container path `/app/logs/` (mounted to host as configured in compose file) |
| Local (no Docker) | `./logs/agent.log` (project root) |

To enable verbose debug logging, set `AGENT_LOG_LEVEL=DEBUG` in your environment or `.env` file.

#### Troubleshooting

**Agent not starting:**
- Verify Alpaca credentials are set correctly in `.env`
- Check that the PostgreSQL database is running: `docker compose ps`
- Review logs for errors: `docker logs trader-momentum-agent`

**No trades being placed:**
- The agent only trades during market hours (9:30 AM - 4:00 PM ET, weekdays)
- Ensure `AGENT_PAPER=true` is set for paper trading (default)
- Check that the momentum thresholds are appropriate for current market conditions

**Permission errors on log files:**
- Use `./start-agents.sh` which creates log directories with correct ownership
- Or manually create the log directory: `mkdir -p ~/projects/algomatic/logs`

### 8. Launch Additional Trading Agents (Optional)

Besides the basic momentum agent, the project includes three additional trading strategy agents that can be run independently:

- **Breakout Agent**: Trades price breakouts above recent highs and breakdowns below recent lows
- **Contrarian Agent**: Takes positions against the prevailing momentum (mean reversion)
- **VWAP Agent**: Trades based on distance from Volume Weighted Average Price

#### Running Multiple Agents

Use the `start-agents.sh` script or Docker Compose directly:

```bash
# Start infrastructure first
docker compose up -d postgres

# Using start-agents.sh (recommended):
./start-agents.sh -d                              # Start all agents
./start-agents.sh -d breakout-agent vwap-agent   # Start specific agents

# Or using Docker Compose directly:
docker compose -f docker-compose.agents.yml up -d                          # All agents
docker compose -f docker-compose.agents.yml up -d breakout-agent vwap-agent  # Specific agents

# View logs for a specific agent
docker logs -f trader-breakout-agent
docker logs -f trader-contrarian-agent
docker logs -f trader-vwap-agent
```

#### Agent Log Locations

| Agent | Container Name | Log Directory (via `start-agents.sh`) |
|---|---|---|
| Momentum | `trader-momentum-agent` | `~/projects/algomatic/logs/momentum-agent-logs/` |
| Contrarian | `trader-contrarian-agent` | `~/projects/algomatic/logs/contrarian-agent-logs/` |
| Breakout | `trader-breakout-agent` | `~/projects/algomatic/logs/breakout-agent-logs/` |
| VWAP | `trader-vwap-agent` | `~/projects/algomatic/logs/vwap-agent-logs/` |

#### Agent-Specific Environment Variables

Each agent has its own environment variable prefix:

| Agent | Prefix | Key Feature | Default Thresholds |
|---|---|---|---|
| Momentum | `AGENT_` | `r5` (5-bar return) | long: 0.001, short: -0.001 |
| Contrarian | `CONTRARIAN_` | `r5` | long: -0.001, short: 0.001 |
| Breakout | `BREAKOUT_` | `breakout_20` (distance from 20-bar high) | long: 0.001, short: -0.02 |
| VWAP | `VWAP_` | `dist_vwap_60` (distance from VWAP) | long: 0.005, short: -0.005 |


### 9. Run the Market Data Service

The market data service is a Go-based background process that fetches OHLCV bars from Alpaca on a schedule and listens for `MARKET_DATA_REQUEST` events via Redis. It replaces ad-hoc provider calls with a centralised fetch-and-persist loop.

**Modes:**
- `service` — Periodic fetcher (runs on an interval)
- `listener` — Event-driven fetcher (subscribes to Redis bus)
- `both` (default) — Runs both concurrently

#### Docker Compose (recommended)

```bash
# 1. Ensure infrastructure is running
docker compose up -d postgres redis

# 2. Start the market data service
docker compose up -d marketdata-service

# 3. Check logs
docker logs -f algomatic-marketdata-service
```

#### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ALPACA_API_KEY` | — | Alpaca API key (required) |
| `ALPACA_SECRET_KEY` | — | Alpaca secret key (required) |
| `MARKETDATA_MODE` | `both` | Run mode: `service`, `listener`, or `both` |
| `MARKETDATA_INTERVAL_MINUTES` | `5` | Minutes between scheduled fetches |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | — | PostgreSQL connection (set in `.env`) |
| `REDIS_HOST`, `REDIS_PORT` | `redis`, `6379` | Redis connection for event bus |

#### Log Location

Logs are mounted to `${LOGS_DIR:-./logs}/marketdata-service/` on the host.

### 10. Run the Reviewer Service

The reviewer service is an event-driven Python process that runs behavioral checks against position campaigns. It subscribes to review events on the Redis message bus and persists check results to the database.

**Events handled:**
- `REVIEW_LEG_CREATED` — A new campaign leg was opened
- `REVIEW_CAMPAIGNS_POPULATED` — Campaigns were populated with strategy assignments
- `REVIEW_CONTEXT_UPDATED` — Market context was updated for a campaign
- `REVIEW_RISK_PREFS_UPDATED` — User risk preferences changed

#### Docker Compose (recommended)

```bash
# 1. Ensure infrastructure is running
docker compose up -d postgres redis

# 2. Start the reviewer service
docker compose up -d reviewer-service

# 3. Check logs
docker logs -f algomatic-reviewer-service
```

#### Run locally without Docker

```bash
# Ensure postgres and redis are running
docker compose up -d postgres redis

# Run the reviewer service directly
python -m src.reviewer.main
```

#### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MESSAGING_BACKEND` | `memory` | Set to `redis` for production/Docker |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | — | PostgreSQL connection (set in `.env`) |
| `REDIS_HOST`, `REDIS_PORT` | `redis`, `6379` | Redis connection for event bus |

#### Log Location

Logs are written to `./logs/reviewer-service.log` (both Docker and local modes).

### Starting All Services Together

To run the full platform stack (database, Redis, market data, reviewer, and indicator engine):

```bash
# Start everything
docker compose up -d

# Verify all services are healthy
docker compose ps

# View logs for all services
docker compose logs -f
```

## Messaging & Market Data Service

The pub/sub messaging system decouples market data fetching from all consumers (UI, agent, evaluators). Instead of each component creating its own `DatabaseLoader` with provider credentials, a single `MarketDataOrchestrator` listens for requests on the message bus and delegates to a centralized `MarketDataService`.

### How It Works

```
Producer                    MessageBus                 MarketDataOrchestrator
   │                            │                              │
   │  publish(MARKET_DATA_      │                              │
   │  REQUEST)                  │──────────────────────────────►│
   │                            │                              │
   │                            │          MarketDataService    │
   │                            │          .ensure_data()       │
   │                            │              │                │
   │                            │              ▼                │
   │                            │          Provider.fetch()     │
   │                            │          DB.insert()          │
   │                            │              │                │
   │                            │◄─────────────────────────────│
   │                            │  publish(MARKET_DATA_UPDATED) │
   │                            │                              │
```

1. **Any component** publishes a `MARKET_DATA_REQUEST` event with `symbol`, `timeframes`, `start`, and `end`.
2. The **orchestrator** calls `MarketDataService.ensure_data()` which checks what data exists in the DB, fetches missing ranges from the configured provider (Alpaca or Finnhub), aggregates intraday timeframes from 1Min, and inserts new bars.
3. On success, the orchestrator publishes `MARKET_DATA_UPDATED` for each timeframe that received new data. On failure it publishes `MARKET_DATA_FAILED`.

Publish is **synchronous** -- when `bus.publish()` returns, the data is already in the database. This is required for the evaluate flow where `ContextPackBuilder` must read fresh data immediately after requesting it.

### Automatic Startup

The orchestrator starts automatically in both entry points:

- **Web UI backend** (`ui/backend/api.py`): Started via `@app.on_event("startup")`, stopped on shutdown.
- **Momentum agent** (`src/agent/main.py`): Started before the scheduler loop begins.

No extra configuration is needed beyond the existing provider credentials (`ALPACA_API_KEY`/`ALPACA_SECRET_KEY` or `FINNHUB_API_KEY`).

### Using Fresh Data in Evaluations

`ContextPackBuilder` accepts an `ensure_fresh_data` flag (default `False`):

```python
# Existing behaviour — reads whatever is in the DB
builder = ContextPackBuilder()

# New — publishes a MARKET_DATA_REQUEST before reading from DB
builder = ContextPackBuilder(ensure_fresh_data=True)
```

The `/api/trading-buddy/evaluate` endpoint uses `ensure_fresh_data=True` so that stale data is automatically refreshed before building market context.

### Publishing Requests Manually

Any component can request data without importing the service directly:

```python
from src.messaging import Event, EventType, get_message_bus

bus = get_message_bus()
bus.publish(Event(
    event_type=EventType.MARKET_DATA_REQUEST,
    payload={
        "symbol": "AAPL",
        "timeframes": ["1Min", "5Min", "1Day"],
        "start": None,  # provider decides
        "end": None,     # defaults to now
    },
    source="my_component",
))
# When this returns, data is in the DB and ready to query.
```

### Testing

The messaging bus provides `reset_message_bus()` for test isolation:

```python
from src.messaging import reset_message_bus

def setup_function():
    reset_message_bus()  # fresh bus for each test
```

Subscriber errors are isolated — one failing callback does not prevent other subscribers from being notified.

## Broker Trade Sync

The platform syncs trade fills from connected brokers to build trade history and enable post-trade analysis.

### Alpaca Direct Integration

For users with Alpaca paper or live trading accounts, trade fills are synced directly via the Alpaca API:

- **On-Login Sync**: When a user authenticates (`/api/auth/me`), a background task automatically syncs any new trade fills from Alpaca.
- **Manual Sync**: Call `POST /api/alpaca/sync` to force a sync.
- **Sync Status**: Check `GET /api/alpaca/status` for connection status and last sync time.
- **Trade History**: Fetch synced trades via `GET /api/alpaca/trades`.

The sync is idempotent — duplicate fills are detected via `external_trade_id` and skipped.

### SnapTrade Integration

For multi-broker support, SnapTrade provides a universal connection layer:

- **Connect Broker**: `POST /api/broker/connect` generates a connection link.
- **Sync Trades**: `POST /api/broker/sync` fetches activities from all connected brokers.
- **Trade History**: `GET /api/broker/trades` returns synced trades.

### TODO: Webhook Integration for Live Trading

> **Note**: The current sync mechanism is polling-based (on-login + manual). For production live trading, implement Alpaca webhooks for real-time trade fill notifications:
>
> 1. Set up a publicly accessible webhook endpoint (`/api/alpaca/webhook`)
> 2. Register the webhook with Alpaca for `trade_updates` events
> 3. Process `fill` events to insert trades in real-time
> 4. This eliminates sync delays and reduces API polling overhead
>
> See: https://docs.alpaca.markets/docs/streaming-trade-updates

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
│   │   ├── _data_helpers.py       # Shared cache and loader utilities
│   │   ├── ohlcv.py               # OHLCV data endpoints
│   │   ├── features_api.py        # Feature computation endpoints
│   │   ├── regimes.py             # HMM + PCA regime endpoints
│   │   ├── data_sync.py           # Sync and import endpoints
│   │   ├── analysis.py            # Symbol analysis endpoints
│   │   ├── market_data_api.py     # Market data API (v1 + Go-strats compat)
│   │   ├── strategy_probe.py      # Strategy probe endpoints
│   │   ├── trading_buddy.py       # Trading Buddy REST endpoints
│   │   ├── broker.py              # SnapTrade broker integration
│   │   ├── alpaca.py              # Direct Alpaca trade sync endpoints
│   │   ├── campaigns.py           # Position campaigns and P&L endpoints
│   │   ├── journal.py             # Trade journal endpoints
│   │   ├── auth.py                # Google OAuth authentication endpoints
│   │   ├── auth_middleware.py     # JWT token validation middleware
│   │   └── user_profile.py        # User profile and risk preference endpoints
│   │
│   ├── data/                       # Data loading and storage
│   │   ├── loaders/               # Data loaders
│   │   │   ├── base.py            # Abstract loader interface
│   │   │   ├── csv_loader.py      # Local CSV files
│   │   │   ├── database_loader.py # PostgreSQL database
│   │   │   ├── alpaca_loader.py   # Alpaca API
│   │   │   └── multi_asset.py     # Multi-asset loading with timestamp alignment
│   │   ├── database/              # SQLAlchemy models and repositories
│   │   │   ├── connection.py      # DatabaseManager, session handling
│   │   │   ├── models.py          # Core models (Ticker, OHLCVBar, etc.)
│   │   │   ├── broker_models.py   # Broker integration (BrokerConnection, TradeFill)
│   │   │   ├── trading_buddy_models.py  # Trading Buddy (UserAccount, TradeIntent, etc.)
│   │   │   ├── strategy_models.py # User-defined strategies
│   │   │   ├── trade_lifecycle_models.py  # Position lots, campaigns, legs
│   │   │   ├── market_repository.py   # Market data access layer
│   │   │   └── trading_repository.py  # Trading Buddy data access layer
│   │   ├── cache.py               # Data caching
│   │   ├── schemas.py             # Pandera OHLCV schema
│   │   └── quality.py             # Data quality checks
│   │
│   ├── messaging/                  # In-memory pub/sub message bus
│   │   ├── events.py              # Event, EventType (REQUEST/UPDATED/FAILED)
│   │   └── bus.py                 # MessageBus, get_message_bus singleton
│   │
│   ├── marketdata/                 # Market data provider abstraction
│   │   ├── base.py                # MarketDataProvider ABC
│   │   ├── alpaca_provider.py     # Alpaca data provider
│   │   ├── finnhub_provider.py    # Finnhub data provider
│   │   ├── service.py             # MarketDataService (ensure_data, gap detection)
│   │   ├── orchestrator.py        # MarketDataOrchestrator (bus <-> service)
│   │   └── utils.py               # Rate limiter, retry, normalisation
│   │
│   ├── features/                   # Feature engineering
│   │   ├── base.py                # Abstract feature interface
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
│   │       │   ├── labeling.py    # State labeling
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
│   ├── execution/                  # Live trading execution
│   │   ├── client.py              # Alpaca client wrapper
│   │   ├── orders.py              # Order types and status
│   │   ├── order_manager.py       # Order lifecycle
│   │   ├── order_tracker.py       # Order tracking
│   │   ├── risk_manager.py        # Risk checks
│   │   ├── runner.py              # Trading runner
│   │   └── snaptrade_client.py    # SnapTrade broker client
│   │
│   ├── reviewer/                   # Reviewer service (event-driven checks)
│   │   ├── main.py                # Standalone entry point
│   │   ├── orchestrator.py        # Event subscriber and check dispatcher
│   │   └── publisher.py           # Review event publishing helpers
│   │
│   └── utils/                      # Utilities
│       └── logging.py             # Centralized logging setup
│
├── tests/                          # Test suite
│   ├── conftest.py                # Shared fixtures
│   ├── unit/
│   │   ├── backtest/              # Backtest tests
│   │   ├── broker/                # Broker integration tests
│   │   ├── data/                  # Data layer tests
│   │   ├── evaluators/            # Evaluator tests
│   │   ├── execution/             # Execution tests
│   │   ├── features/              # Feature tests
│   │   └── hmm/                   # HMM module tests
│   └── integration/
│       ├── test_strategy_parity.py   # Python/Go condition parity tests
│       ├── test_data_pipeline.py     # Aggregation, tz, feature tests
│       └── test_reviewer_flow.py     # Reviewer event flow tests
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
│       ├── 001_initial_schema.py
│       ├── 002_add_computed_features.py
│       ├── 003_remove_vwap.py
│       ├── 004_consolidate_states_to_features.py
│       ├── 005_trading_buddy_tables.py
│       ├── 006_broker_integration_tables.py
│       ├── 007_auth_and_user_profiles.py
│       ├── 008_trade_lifecycle_schema.py
│       ├── 009_position_campaigns.py
│       ├── 010_strategies_first_class.py
│       ├── 011_user_profiles_jsonb.py
│       ├── 012_strategy_risk_profiles.py
│       ├── 013_settings_journal_schema.py
│       ├── 014_site_preferences.py
│       ├── 015_strategy_probe_tables.py
│       ├── 016_strategy_probe_trades.py
│       ├── 017_add_trade_pnl_metrics.py
│       ├── 018_fix_open_day_to_date.py
│       ├── 019_campaign_checks.py
│       ├── 020_add_strategy_versioning.py
│       └── 021_add_probe_results_open_day_index.py
│
├── ui/                             # Web UI
│   ├── backend/                   # FastAPI backend (api.py)
│   ├── frontend/                  # React + TypeScript frontend
│   ├── run_backend.py             # Backend entry point
│   ├── start_ui.sh                # Linux/macOS startup script
│   └── start_ui.bat               # Windows startup script
│
├── scripts/                        # CLI scripts
│   ├── helpers/                   # Shared helper modules
│   │   ├── data.py                # Data loading helpers
│   │   ├── logging_setup.py       # Logging configuration
│   │   └── output.py              # Output formatting helpers
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
├── Dockerfile                      # Docker image for trading agents and reviewer service
├── docker-compose.yml              # Core services (postgres, redis, indicator-engine, marketdata-service, reviewer-service, pgAdmin)
├── docker-compose.agents.yml       # Trading agent services (momentum, breakout, etc.)
│
├── marketdata-service/              # Go-based market data fetch service
│   ├── cmd/marketdata-service/    # Entry point (service, listener, or both modes)
│   ├── internal/                  # Internal packages (alpaca, db, redisbus, service)
│   └── Dockerfile                 # Multi-stage Go build
│
├── go-strats/                      # Go strategy backtesting framework (experimental)
│   ├── cmd/                       # CLI entry points
│   └── pkg/                       # Core packages (api, backend, conditions, engine, etc.)
│
├── indicator-engine/               # High-performance C++ indicator computation engine
│   ├── src/                       # Source files (indicators, pipeline, service)
│   └── tests/                     # Unit tests
│
├── proposed-ui/                    # Proposed React UI scaffold for Position Campaigns
│   └── src/                       # React components with mock data
│
└── docs/                           # Documentation
    ├── ARCHITECTURE.md            # System design and data flow
    ├── APIs.md                    # REST API reference
    ├── DATABASE.md                # Database schema, migrations, and configuration
    ├── FEATURE.md                 # Feature engineering specification
    ├── PRD.md                     # Product requirements document
    ├── PITFALLS.md                # ML and trading pitfalls research
    ├── STRATEGIES_REPO.md         # 100 TA-Lib based trading strategies
    └── archive/                   # Historical design documents
        ├── STATE_VECTOR_HMM_IMPLEMENTATION_PLAN.md
        ├── Trading_Buddy_Master_Roadmap_and_DB_Schema.md
        ├── Trading_Buddy_Detailed_TODOs.md
        ├── tradingbuddy_trade_schema.md
        ├── position_campaigns_ui_schema_plan.md
        └── strategy_service_design.md
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
- [Strategy Repository](docs/STRATEGIES_REPO.md): 100 TA-Lib based trading strategies

### Archive

Older design documents are available in `docs/archive/`:
- [HMM Implementation Plan](docs/archive/STATE_VECTOR_HMM_IMPLEMENTATION_PLAN.md): Phase-by-phase HMM implementation
- [Trading Buddy Roadmap](docs/archive/Trading_Buddy_Master_Roadmap_and_DB_Schema.md): Evaluation platform architecture
- [Trading Buddy TODOs](docs/archive/Trading_Buddy_Detailed_TODOs.md): Detailed implementation status
- [Trade Schema](docs/archive/tradingbuddy_trade_schema.md): Trade schema documentation
- [Position Campaigns Plan](docs/archive/position_campaigns_ui_schema_plan.md): Position campaigns UI plan
- [Strategy Service Design](docs/archive/strategy_service_design.md): Strategy service architecture

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Make your changes following PEP 8 style
4. Write tests for new functionality
5. Commit with meaningful messages
6. Push and create a Pull Request
