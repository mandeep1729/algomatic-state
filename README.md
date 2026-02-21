# Algomatic State

Trading copilot platform combining HMM-based market regime tracking with a modular trade evaluation system (Trading Buddy) that surfaces risk, context, and inconsistencies to improve trading decisions.

## Overview

Algomatic State has the following major subsystems:

1. **Regime Tracking Engine** -- Multi-timeframe Hidden Markov Model (HMM) approach to market state inference. The system learns continuous latent state vectors from engineered features and uses Gaussian HMMs to infer discrete market regimes.

2. **Trading Buddy (Trade Evaluation)** -- A modular evaluator orchestrator that reviews proposed trades against risk/reward checks, exit plan quality, regime fit, multi-timeframe alignment, and guardrails. Acts as a mentor and risk guardian, not a signal generator.

3. **Messaging & Market Data Service** -- An in-memory pub/sub message bus (`src/messaging/`) decouples market data fetching from consumers. A centralized `MarketDataService` handles gap detection, provider fetching, and DB persistence. The `MarketDataOrchestrator` wires the two together so that any component can request fresh data by publishing a `MARKET_DATA_REQUEST` event.

### Key Features

- **Multi-Timeframe Support**: Separate models for 1Min, 15Min, 1Hour, and 1Day timeframes
- **Anti-Chatter Controls**: Minimum dwell time, probability thresholds, majority voting
- **OOD Detection**: Log-likelihood based out-of-distribution detection
- **Walk-Forward Validation**: Time-based cross-validation with leakage prevention
- **Production Monitoring**: Drift detection, shadow inference, retraining triggers
- **Trade Evaluation**: Pluggable evaluator modules (risk/reward, exit plan, regime fit, MTFA)
- **Broker Integration**: SnapTrade-based broker connection and direct Alpaca API for trade history sync
- **Go Agent Service**: Manages trading agent lifecycle, strategy resolution, and order execution via Alpaca
- **Portal UI**: Full SPA with public pages, authentication, trade investigation/insights, agent management, and settings


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

### 4. Start the Web UI

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

### 5. Trading Agents

Trading agents are managed through the **Go agent-service** (`agent-service/`), which runs as part of the main Docker Compose stack. Agents are created, configured, and controlled via the Portal UI (Agents page) or the REST API (`/api/trading-agents/`).

The agent-service supports 100+ predefined strategies, agent lifecycle management (start/pause/stop), and tracks all orders and activity in the database. See `agent-service/` for implementation details and `src/api/trading_agents.py` for the API endpoints.

### 6. Run the Market Data Service

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

### 7. Run the Reviewer Service

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

The orchestrator starts automatically in the web UI backend:

- **Web UI backend** (`ui/backend/api.py`): Started via `@app.on_event("startup")`, stopped on shutdown.

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

None
