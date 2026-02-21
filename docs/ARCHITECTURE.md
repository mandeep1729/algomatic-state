# Architecture Document: Algomatic State

## System Overview

Algomatic State follows a layered architecture with clear separation between data ingestion, feature engineering, state representation, strategy logic, and execution. Each layer communicates through well-defined interfaces, enabling independent testing and evolution.

```
┌─────────────────────────────────────────────────────────────────┐
│                      Configuration Layer                         │
│                   (Pydantic Settings, YAML)                     │
└─────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼───────────────────────────────┐
│                               ▼                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │   Alpaca    │    │  Database   │    │    CSV      │       │
│  │   Loader    │    │   Loader    │    │   Loader    │       │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘       │
│         └──────────────────┼──────────────────┘               │
│                            ▼                                  │
│                   Data Validation Layer                       │
│                                                               │
│                        DATA LAYER                             │
└───────────────────────────────┼───────────────────────────────┘
                                │
┌───────────────────────────────┼───────────────────────────────┐
│                               ▼                               │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────┐     │
│  │ Returns │ │Volatility│ │ Volume │ │  TA Indicators  │     │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────────┬────────┘     │
│       └───────────┴───────────┴───────────────┘               │
│                            ▼                                  │
│                   Feature Pipeline                            │
│                                                               │
│                     FEATURE LAYER                             │
└───────────────────────────────┼───────────────────────────────┘
                                │
┌───────────────────────────────┼───────────────────────────────┐
│                               ▼                               │
│         ┌─────────────────────────────────────┐               │
│         │           Scaler (per TF)           │               │
│         └──────────────────┬──────────────────┘               │
│                            ▼                                  │
│         ┌────────────┬─────┴─────┬────────────┐               │
│         │    PCA     │           │  Temporal  │               │
│         │  Encoder   │           │     AE     │               │
│         └─────┬──────┘           └──────┬─────┘               │
│               └──────────┬──────────────┘                     │
│                          ▼                                    │
│    ┌─────────────────────────────────────────────────────┐   │
│    │                 State Computation                    │   │
│    │  ┌─────────────────────┐  ┌─────────────────────┐   │   │
│    │  │    Gaussian HMM     │  │   PCA + K-means     │   │   │
│    │  │ (Regime Inference)  │  │ (Simpler approach)  │   │   │
│    │  └──────────┬──────────┘  └──────────┬──────────┘   │   │
│    │             └──────────┬─────────────┘              │   │
│    └─────────────────────────┼───────────────────────────┘   │
│                              ▼                                │
│                   State + Regime Output                       │
│                                                               │
│                      STATE LAYER                              │
└───────────────────────────────┼───────────────────────────────┘
                                │
┌───────────────────────────────┼───────────────────────────────┐
│                               ▼                               │
│         ┌─────────────────────────────────────┐               │
│         │         Trading Strategy            │               │
│         │   (Regime-gated signal generation)  │               │
│         └──────────────────┬──────────────────┘               │
│                            ▼                                  │
│                    Signal Generator                           │
│                                                               │
│                     STRATEGY LAYER                            │
└───────────────────────────────┼───────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│   Backtest    │     │    Paper      │     │     Live      │
│    Engine     │     │    Trader     │     │    Trader     │
├───────────────┤     ├───────────────┤     ├───────────────┤
│ Walk-Forward  │     │ Risk Manager  │     │ Risk Manager  │
│  Validator    │     │ Order Manager │     │ Order Manager │
│   Metrics     │     │ Alpaca Client │     │ Alpaca Client │
└───────────────┘     └───────────────┘     └───────────────┘

        BACKTEST                EXECUTION LAYER
```

## Directory Structure

```
algomatic-state/
├── config/                     # Configuration files
│   ├── __init__.py
│   ├── settings.py             # Pydantic settings classes
│   ├── features.json           # Feature configuration
│   ├── assets.yaml             # Asset universe
│   ├── trading.yaml            # Trading strategy and backtest config
│   ├── state_vector_feature_spec.yaml  # HMM feature spec
│   └── seed/                   # Database seed data (initial tickers, etc.)
│
├── proto/                      # Protobuf definitions (shared between Go services and Python)
│   ├── market/v1/              # Market data service protos
│   │   ├── ticker.proto
│   │   ├── bar.proto
│   │   ├── feature.proto
│   │   ├── sync_log.proto
│   │   └── service.proto
│   └── probe/v1/               # Probe data service protos
│       └── service.proto
│
├── data-service/               # Go gRPC data-service (owns market data tables)
│   ├── cmd/data-service/       # Entry point (main.go)
│   ├── internal/
│   │   ├── config/             # Configuration
│   │   ├── db/                 # Database connection pool (pgx)
│   │   ├── repository/         # Market data + probe repositories
│   │   └── server/             # gRPC server implementations
│   ├── Dockerfile
│   ├── go.mod / go.sum
│   └── proto/gen/go/           # Generated Go gRPC stubs
│
├── marketdata-service/         # Go market data aggregator (fetches from Alpaca, writes via gRPC)
│   ├── cmd/marketdata-service/ # Entry point
│   ├── internal/
│   │   ├── aggregator/         # Timeframe aggregation
│   │   ├── alpaca/             # Alpaca API client
│   │   ├── config/             # Configuration
│   │   ├── dataclient/         # gRPC client to data-service
│   │   ├── redisbus/           # Redis pub/sub integration
│   │   └── service/            # Orchestration service
│   └── Dockerfile
│
├── indicator-engine/           # C++ high-performance indicator computation
│   ├── src/                    # Source files (indicators, pipeline, gRPC service)
│   ├── tests/                  # Unit tests
│   └── Dockerfile
│
├── go-strats/                  # Go strategy backtesting framework
│   ├── cmd/probe/              # CLI entry point
│   └── pkg/                    # Core packages (api, backend, conditions, engine, persistence)
│
├── agent-service/              # Go agent service (manages trading agent lifecycle)
│   ├── cmd/agent-service/      # Entry point (main.go)
│   ├── internal/
│   │   ├── alpaca/             # Alpaca trading client
│   │   ├── config/             # Configuration
│   │   ├── db/                 # Database connection pool (pgx)
│   │   ├── repository/         # Agent, order, activity, strategy repositories
│   │   ├── runner/             # Agent loop orchestrator and signal computation
│   │   └── strategy/           # Strategy resolver (compiles JSONB DSL)
│   └── Dockerfile
│
├── src/                        # Python source code
│   ├── __init__.py
│   │
│   ├── api/                    # Public API routers
│   │   ├── trading_buddy.py    # Trading Buddy REST endpoints
│   │   ├── broker.py           # SnapTrade broker integration routes
│   │   ├── alpaca.py           # Direct Alpaca trade sync endpoints
│   │   ├── campaigns.py        # Position campaigns and P&L endpoints
│   │   ├── strategies.py       # User-defined trading strategies CRUD
│   │   ├── strategy_probe.py   # Strategy probe endpoints
│   │   ├── journal.py          # Trade journal endpoints
│   │   ├── waitlist.py         # Waitlist submission endpoints
│   │   ├── auth.py             # Google OAuth authentication endpoints
│   │   ├── auth_middleware.py   # JWT token validation middleware
│   │   ├── user_profile.py     # User profile and risk preference endpoints
│   │   ├── _data_helpers.py    # Shared data utilities (feature computation)
│   │   ├── market_data.py      # Market data endpoints (v1)
│   │   ├── market_data_api.py  # Market data endpoints (v2)
│   │   ├── data_sync.py        # Data sync endpoints
│   │   ├── analysis.py         # HMM analysis endpoints
│   │   ├── regimes.py          # Regime state endpoints (HMM + PCA)
│   │   ├── trading_agents.py   # Trading agent CRUD, lifecycle, and order endpoints
│   │   └── internal.py         # Internal/admin endpoints
│   │
│   ├── data/                   # Data layer
│   │   ├── __init__.py
│   │   ├── grpc_client.py      # MarketDataGrpcClient (drop-in replacement for OHLCVRepository)
│   │   ├── timeframe_aggregator.py # Build higher-TF bars from 1Min data
│   │   ├── loaders/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # Abstract loader interface
│   │   │   ├── csv_loader.py   # Local CSV files
│   │   │   ├── database_loader.py # DatabaseLoader (uses gRPC for market data access)
│   │   │   ├── alpaca_loader.py # Alpaca API
│   │   │   └── multi_asset.py  # Multi-asset loading with timestamp alignment
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── connection.py   # Database connection and session management
│   │   │   ├── dependencies.py # FastAPI DI + context managers (get_db, get_*_repo, grpc_market_client)
│   │   │   ├── models.py       # Core models (Ticker, OHLCVBar, DataSyncLog, ComputedFeature)
│   │   │   ├── broker_models.py # Broker integration (BrokerConnection, TradeFill, SnapTradeUser)
│   │   │   ├── trading_buddy_models.py # Trading Buddy (UserAccount, UserProfile, UserRule, Waitlist)
│   │   │   ├── strategy_models.py # User-defined trading strategies
│   │   │   ├── trade_lifecycle_models.py # DecisionContext, CampaignCheck, CampaignFill
│   │   │   ├── journal_models.py  # Journal entries
│   │   │   ├── probe_models.py    # Strategy probe tables
│   │   │   ├── market_repository.py   # OHLCVRepository (legacy, used only for Alembic/testing)
│   │   │   ├── trading_repository.py  # TradingBuddyRepository (user accounts, profiles, strategies)
│   │   │   ├── broker_repository.py   # BrokerRepository (fills, contexts, connections, P&L)
│   │   │   ├── journal_repository.py  # JournalRepository (journal CRUD)
│   │   │   └── probe_repository.py    # ProbeRepository (strategy probe aggregations)
│   │   ├── cache.py            # Data caching
│   │   ├── schemas.py          # Pandera OHLCV schema validation
│   │   └── quality.py          # Data quality checks
│   │
│   ├── messaging/              # Pub/sub message bus (in-memory + Redis backends)
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract MessageBusBackend ABC
│   │   ├── events.py           # Event, EventType
│   │   ├── bus.py              # MessageBus, get_message_bus singleton
│   │   ├── redis_bus.py        # Redis-backed message bus implementation
│   │   └── serialization.py   # Event serialization for Redis transport
│   │
│   ├── marketdata/             # Market data provider abstraction
│   │   ├── __init__.py
│   │   ├── base.py             # MarketDataProvider ABC
│   │   ├── alpaca_provider.py  # Alpaca data provider
│   │   ├── finnhub_provider.py # Finnhub data provider
│   │   ├── service.py          # MarketDataService (ensure_data, gap detection, uses gRPC)
│   │   ├── orchestrator.py     # MarketDataOrchestrator (bus <-> service)
│   │   └── utils.py            # Rate limiter, retry, normalisation
│   │
│   ├── trade/                  # Domain objects
│   │   ├── intent.py           # TradeIntent with validation and computed properties
│   │   └── evaluation.py       # EvaluationResult, EvaluationItem, Severity, Evidence
│   │
│   ├── rules/                  # Compliance & Guardrails
│   │   └── guardrails.py       # Output sanitisation (no-prediction policy)
│   │
│   ├── evaluators/             # Trade evaluation engine
│   │   ├── base.py             # Evaluator ABC with EvaluatorConfig
│   │   ├── registry.py         # @register_evaluator decorator, get_evaluator()
│   │   ├── evidence.py         # Evidence helpers (z-scores, thresholds, ATR)
│   │   ├── context.py          # ContextPack, ContextPackBuilder (bars, features, regimes, levels)
│   │   ├── risk_reward.py      # Risk/Reward evaluator (R:R, sizing, stop distance)
│   │   ├── exit_plan.py        # Exit plan evaluator (stop/target presence, proximity)
│   │   ├── regime_fit.py       # Regime fit evaluator (direction conflict, transition risk, OOD)
│   │   ├── mtfa.py             # Multi-timeframe alignment evaluator
│   │   ├── stop_placement.py   # Stop placement evaluator (stop vs structure, ATR distance)
│   │   ├── structure_awareness.py # Structure awareness evaluator (support/resistance proximity)
│   │   └── volatility_liquidity.py # Volatility and liquidity evaluator (spread, volume, vol regime)
│   │
│   ├── orchestrator.py         # EvaluatorOrchestrator (sequential/parallel execution, scoring)
│   │
│   ├── trading_agents/         # Trading agent management
│   │   ├── __init__.py
│   │   ├── models.py           # AgentStrategy, TradingAgent, AgentOrder, AgentActivityLog models
│   │   ├── repository.py       # TradingAgentsRepository (CRUD for agents, orders, activity)
│   │   └── predefined.py       # Predefined strategy catalog
│   │
│   ├── features/               # Feature engineering
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract feature interface
│   │   ├── returns.py          # Return-based features
│   │   ├── volatility.py       # Volatility features
│   │   ├── volume.py           # Volume features
│   │   ├── intrabar.py         # Intrabar structure features
│   │   ├── time_of_day.py      # Time-of-day encoding
│   │   ├── market_context.py   # Market context features
│   │   ├── anchor.py           # Anchor VWAP features
│   │   ├── talib_indicators.py # TA-Lib indicators
│   │   ├── pandas_ta_indicators.py # pandas-ta indicators
│   │   ├── pipeline.py         # Feature orchestration
│   │   ├── registry.py         # Feature registry
│   │   └── state/              # State representation modules
│   │       ├── __init__.py
│   │       ├── hmm/            # HMM regime tracking
│   │       │   ├── __init__.py
│   │       │   ├── contracts.py    # FeatureVector, HMMOutput, ModelMetadata
│   │       │   ├── config.py       # Configuration loading
│   │       │   ├── artifacts.py    # Model artifact management
│   │       │   ├── scalers.py      # Robust, Standard, Yeo-Johnson scalers
│   │       │   ├── encoders.py     # PCA and Temporal PCA encoders
│   │       │   ├── hmm_model.py    # Gaussian HMM wrapper
│   │       │   ├── data_pipeline.py # Feature loading, gap handling, splitting
│   │       │   ├── training.py     # Training pipeline
│   │       │   ├── inference.py    # Online inference engine
│   │       │   ├── labeling.py     # State labeling
│   │       │   ├── storage.py      # Parquet state storage
│   │       │   ├── validation.py   # Model validation and diagnostics
│   │       │   └── monitoring.py   # Drift detection and operations
│   │       └── pca/            # PCA + K-means state computation
│   │           ├── __init__.py
│   │           ├── contracts.py    # PCAStateOutput, PCAModelMetadata
│   │           ├── artifacts.py    # Model path management
│   │           ├── training.py     # PCAStateTrainer
│   │           ├── engine.py       # PCAStateEngine for inference
│   │           └── labeling.py     # Semantic state labeling
│   │
│   ├── backtest/               # Backtesting
│   │   ├── __init__.py
│   │   ├── engine.py           # Backtest engine
│   │   ├── walk_forward.py     # Walk-forward validation
│   │   ├── metrics.py          # Performance metrics
│   │   └── report.py           # Reporting
│   │
│   ├── reviewer/               # Event-driven behavioral checks service
│   │   ├── __init__.py
│   │   ├── main.py             # Standalone entry point
│   │   ├── orchestrator.py     # Event subscriber and check dispatcher
│   │   ├── publisher.py        # Review event publishing helpers
│   │   ├── api_client.py       # API client for reviewer service
│   │   ├── baseline.py         # Baseline check logic
│   │   └── checks/             # Individual check implementations
│   │       ├── __init__.py
│   │       ├── base.py         # BaseCheck ABC
│   │       ├── risk_sanity.py  # Risk sanity checks
│   │       ├── entry_quality.py # Entry quality checks
│   │       └── runner.py       # CheckRunner execution engine
│   │
│   ├── execution/              # Live trading
│   │   ├── __init__.py
│   │   ├── client.py           # Alpaca client wrapper
│   │   ├── orders.py           # Order types and status
│   │   ├── order_manager.py    # Order lifecycle
│   │   ├── order_tracker.py    # Order tracking
│   │   ├── risk_manager.py     # Risk checks
│   │   ├── runner.py           # Trading runner
│   │   └── snaptrade_client.py # SnapTrade broker client
│   │
│   └── utils/                  # Utilities
│       ├── __init__.py
│       └── logging.py          # Centralized logging setup with file logging
│
├── tests/                      # Test suite (80+ test files)
│   ├── conftest.py             # Shared fixtures
│   ├── integration/            # Integration tests
│   │   └── test_data_pipeline.py
│   └── unit/
│       ├── api/                # API endpoint tests (auth, broker, campaigns, strategies, etc.)
│       ├── backtest/           # Backtest engine and metrics tests
│       ├── broker/             # Broker model and SnapTrade client tests
│       ├── checks/             # Behavioral check tests
│       ├── data/               # Data layer tests (loaders, repositories, aggregator)
│       ├── evaluators/         # Evaluator tests (context, mtfa, regime_fit, stop_placement, etc.)
│       ├── execution/          # Execution tests (orders, risk manager, order tracker)
│       ├── features/           # Feature tests (returns, volatility, volume, intrabar, etc.)
│       ├── hmm/                # HMM module tests (artifacts, config, encoders, scalers)
│       ├── marketdata/         # Market data service and orchestrator tests
│       ├── messaging/          # Message bus, events, redis bus, serialization tests
│       ├── reviewer/           # Reviewer orchestrator, publisher, deduplication tests
│       ├── rules/              # Guardrails tests
│       └── trade/              # Trade intent and evaluation tests
│
├── scripts/                    # CLI scripts
│   ├── helpers/                # Shared helper modules
│   │   ├── data.py             # Data loading helpers
│   │   ├── logging_setup.py    # Logging configuration
│   │   └── output.py           # Output formatting helpers
│   ├── download_data.py        # Download OHLCV data from Alpaca
│   ├── download_tickers.py     # Download and seed ticker metadata
│   ├── compute_features.py     # Compute technical features
│   ├── import_csv_to_db.py     # Import CSV/Parquet data to database
│   ├── init_db.py              # Initialize database schema
│   ├── train_hmm.py            # Train HMM regime model
│   ├── analyze_hmm_states.py   # Analyze trained HMM states
│   ├── run_paper_trading.py    # Run paper trading session
│   └── run_live_trading.py     # Run live trading session
│
├── alembic/                    # Database migrations
│   ├── env.py
│   └── versions/               # 40 migrations (001-040)
│
├── ui/                         # Web UI
│   ├── backend/
│   │   └── api.py              # FastAPI backend
│   ├── frontend/               # React + TypeScript frontend
│   │   └── src/portal/         # Portal SPA (100+ components)
│   │       ├── api/            # API client and endpoint wrappers
│   │       ├── components/     # Reusable UI components
│   │       │   ├── agents/     # Agent management (status, orders, create modal)
│   │       │   ├── campaigns/  # Campaign detail (timeline, checks, context)
│   │       │   ├── charts/     # ECharts-based analytics (equity curve, drawdown, heatmaps)
│   │       │   ├── investigate/ # Trade investigation (filters, driver cards, subset metrics)
│   │       │   ├── strategies/ # Strategy form with condition builder
│   │       │   └── ui/         # Generic UI primitives (Section, StatCard)
│   │       ├── context/        # React contexts (Auth, Chart, Investigate)
│   │       ├── layouts/        # Page layouts (App, Public, Onboarding, Root)
│   │       ├── pages/          # Route pages
│   │       │   ├── app/        # Authenticated pages (Dashboard, Campaigns, Agents, Investigate, etc.)
│   │       │   ├── settings/   # Settings pages (Profile, Risk, Strategies, Brokers)
│   │       │   ├── auth/       # Login page
│   │       │   ├── help/       # Help articles
│   │       │   └── public/     # Public pages (Home, FAQ, Pricing, legal)
│   │       ├── routes/         # Route definitions
│   │       └── utils/          # Utility functions (metrics, filters, P&L calculations)
│   ├── run_backend.py          # Backend entry point
│   ├── start_ui.sh             # Linux/macOS startup script
│   └── start_ui.bat            # Windows startup script
│
├── models/                     # Trained models (per ticker/timeframe)
│   └── ticker=AAPL/
│       └── timeframe=1Min/
│           └── model_id=state_v001/
│               ├── scaler.pkl
│               ├── encoder.pkl
│               ├── hmm.pkl
│               ├── metadata.json
│               └── feature_spec.yaml
│
├── Dockerfile                  # Docker image for Python backend + reviewer service
├── docker-compose.yml          # Full stack: postgres, redis, data-service, indicator-engine, marketdata-service, reviewer-service, agent-service
│
└── docs/                       # Documentation
    ├── ARCHITECTURE.md         # System design and data flow
    ├── APIs.md                 # REST API reference
    ├── DATABASE.md             # Database schema and migrations
    ├── FEATURE.md              # Feature engineering specification
    ├── PRD.md                  # Product requirements document
    ├── PITFALLS.md             # ML and trading pitfalls research
    ├── STRATEGIES_REPO.md      # 100 TA-Lib based trading strategies
    ├── TRADE_CHECKS_REFERENCE.md # Behavioral check codes and descriptions
    └── archive/                # Historical design documents
        ├── STATE_VECTOR_HMM_IMPLEMENTATION_PLAN.md
        ├── Trading_Buddy_Master_Roadmap_and_DB_Schema.md
        ├── Trading_Buddy_Detailed_TODOs.md
        ├── tradingbuddy_trade_schema.md
        ├── position_campaigns_ui_schema_plan.md
        └── strategy_service_design.md
```

## Core Components

### 1. Data Layer & gRPC Architecture

**Purpose**: Load, validate, and cache OHLCV market data from multiple sources. All market data access flows through the Go data-service via gRPC.

#### Data Access Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Python Backend                          │
│                                                            │
│  FastAPI Routes ──► Depends(get_market_grpc_client)        │
│  Background Services ──► grpc_market_client() ctx mgr      │
│                              │                             │
│              MarketDataGrpcClient (src/data/grpc_client.py)│
└──────────────────────────────┼─────────────────────────────┘
                               │ gRPC (port 50051)
┌──────────────────────────────┼─────────────────────────────┐
│              Go data-service (data-service/)                │
│                                                             │
│  MarketDataService (gRPC server)                           │
│       │                                                     │
│       ├──► ticker_repo.go    → tickers table               │
│       ├──► bar_repo.go       → ohlcv_bars table            │
│       ├──► feature_repo.go   → computed_features table     │
│       ├──► sync_log_repo.go  → data_sync_log table         │
│       └──► probe_*_repo.go   → probe tables                │
│                              │                              │
│              PostgreSQL (pgx connection pool)               │
└─────────────────────────────────────────────────────────────┘
```

**Key principle**: Market data tables (`tickers`, `ohlcv_bars`, `computed_features`, `data_sync_log`, `probe_strategies`, `strategy_probe_results`, `strategy_probe_trades`) are owned exclusively by the Go data-service. All reads and writes go through gRPC. Trading tables (`user_accounts`, `user_profiles`, `trade_fills`, `decision_contexts`, `strategies`, `campaigns`, `journal_entries`, etc.) are accessed directly by Python via SQLAlchemy repositories.

#### Python Repository Layer

| Repository | Domain | Access Pattern |
|------------|--------|----------------|
| `MarketDataGrpcClient` | Market data (bars, features, tickers, sync logs) | gRPC to data-service |
| `TradingBuddyRepository` | User accounts, profiles, strategies | Direct SQLAlchemy |
| `BrokerRepository` | Fills, decision contexts, broker connections, P&L | Direct SQLAlchemy |
| `JournalRepository` | Journal entries | Direct SQLAlchemy |
| `ProbeRepository` | Strategy probe aggregation queries | Direct SQLAlchemy |

All repositories are injected via FastAPI `Depends()` functions defined in `src/data/database/dependencies.py`.

#### BaseDataLoader (Abstract)
```python
class BaseDataLoader(ABC):
    @abstractmethod
    def load(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Load OHLCV data for a single symbol."""
        pass

    @abstractmethod
    def load_multiple(self, symbols: list[str], start: datetime, end: datetime) -> dict[str, pd.DataFrame]:
        """Load OHLCV data for multiple symbols."""
        pass
```

**Implementations**:
- `CSVLoader`: Reads local CSV files with configurable date parsing
- `AlpacaLoader`: Fetches historical bars from Alpaca API with pagination
- `DatabaseLoader`: Loads from database via gRPC, with auto-fetch from Alpaca for missing data

**Data Schema** (enforced via pandera):
```
- timestamp: datetime64[ns] (index, timezone-aware)
- open: float64 (positive)
- high: float64 (>= open, >= close)
- low: float64 (<= open, <= close)
- close: float64 (positive)
- volume: int64 (non-negative)
```

### 2. Feature Layer

**Purpose**: Compute stable, interpretable features from raw OHLCV data.

#### BaseFeature (Abstract)
```python
class BaseFeature(ABC):
    def __init__(self, name: str, params: dict = None):
        self.name = name
        self.params = params or {}

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.Series:
        """Compute feature from OHLCV DataFrame."""
        pass

    @property
    @abstractmethod
    def lookback(self) -> int:
        """Minimum rows needed to compute this feature."""
        pass
```

#### Feature Categories

| Category | Features | Description |
|----------|----------|-------------|
| Returns | r1, r5, r15, r60, cumret_60, ema_diff, slope_60, trend_strength | Price change and trend measures |
| Volatility | rv_15, rv_60, range_1, atr_60, range_z_60, vol_of_vol | Price dispersion and range measures |
| Volume | vol1, dvol1, relvol_60, vol_z_60, dvol_z_60 | Trading activity and participation measures |
| Intrabar | clv, body_ratio, upper_wick, lower_wick | Candle structure and shape measures |
| Time of Day | tod_sin, tod_cos, is_open_window, is_close_window, is_midday | Time-based session encoding |
| Market Context | mkt_r5, mkt_r15, mkt_rv_60, beta_60, resid_rv_60 | Broad market and relative measures |

#### FeaturePipeline
Orchestrates feature computation with:
- Parallel computation of independent features
- Automatic lookback period handling
- Optional caching of computed features
- Feature correlation analysis

### 3. State Layer (HMM Module)

**Purpose**: Learn continuous latent state vectors and infer discrete market regimes.

**Location**: `src/features/state/hmm/` (HMM) and `src/features/state/pca/` (PCA + K-means alternative)

#### Architecture (per timeframe)
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
Latent State z_t ∈ R^d (d ∈ [6,16])
     │
     ▼
Gaussian HMM
     │
     ├─► Filtered Posterior α_t(k) = p(s_t=k | z_{1:t})
     │
     └─► Discrete Regime s_t ∈ {1..K}
```

#### Multi-Timeframe Design
- Separate models per timeframe: 1Min, 15Min, 1Hour, 1Day
- Different K (state count) per timeframe
- Higher TF states for risk-on/off; lower TF for timing

#### Key Components (all under `src/features/state/hmm/`)
- **Scalers** (`scalers.py`): RobustScaler (median/IQR), StandardScaler, YeoJohnsonScaler, CombinedScaler
- **Encoders** (`encoders.py`): PCAEncoder, TemporalPCAEncoder with auto latent dimension selection
- **HMM** (`hmm_model.py`): GaussianHMMWrapper with K-means init, covariance regularization, AIC/BIC selection
- **Training** (`training.py`): TrainingPipeline, CrossValidator, HyperparameterTuner
- **Inference** (`inference.py`): InferenceEngine with anti-chatter and OOD detection
- **Validation** (`validation.py`): DwellTimeAnalyzer, TransitionAnalyzer, PosteriorAnalyzer
- **Monitoring** (`monitoring.py`): DriftDetector, ShadowInference, RetrainingScheduler

### 4. Strategy Layer

**Purpose**: Generate trading signals using regime-aware logic from HMM states.

#### Target Signal Flow
```
Market Data
     │
     ├─► Features ─► Base Signal (momentum/mean-reversion)
     │
     └─► HMM State ─► Regime Classification
                            │
                            ▼
                     Regime-Gated Filter
                            │
                            ▼
                     Position Sizer (regime-adjusted)
                            │
                            ▼
                     Final Signal
```

#### Hierarchical Usage Pattern
- **1h/1d states**: Risk-on/off filter + position sizing
- **15m/5m states**: Trend quality / chop filter
- **1m states**: Entry timing / stop logic

#### Signal Types (Placeholder)
```python
@dataclass
class Signal:
    timestamp: datetime
    symbol: str
    direction: Literal["long", "short", "flat"]
    strength: float        # 0.0 to 1.0
    size: float           # Dollar amount or shares
    metadata: dict        # Regime info, state_id, state_prob
```

### 5. Backtest Layer

**Purpose**: Simulate strategy performance on historical data.

#### BacktestEngine
```python
class BacktestEngine:
    def run(self, data: dict[str, pd.DataFrame], strategy: BaseStrategy) -> BacktestResult:
        """
        Event loop:
        1. For each timestamp in data
        2. Update strategy with new bar
        3. Generate signals
        4. Execute fills from previous signals
        5. Update positions and P&L
        6. Apply slippage and commission
        """
```

#### Walk-Forward Validation
```
|----Train----|--Test--|
              |----Train----|--Test--|
                            |----Train----|--Test--|
                                          |----Train----|--Test--|

Timeline ──────────────────────────────────────────────────────►
```

- Train window: 6 months (configurable)
- Test window: 1 month (configurable)
- Step: 1 month (configurable)
- At each step: retrain state model, refit strategy, evaluate OOS

### 6. Execution Layer

**Purpose**: Execute trades via Alpaca API with risk controls.

#### Order Flow
```
Signal
   │
   ▼
Risk Manager ──► REJECT (if limits exceeded)
   │
   │ APPROVE
   ▼
Position Sizer
   │
   ▼
Order Manager
   │
   ▼
Alpaca Client ──► Submit Order
   │
   ▼
Fill Handler ──► Update Positions
```

#### Risk Controls
| Control | Description | Action |
|---------|-------------|--------|
| Position Limit | Max 10% in single asset | Reject order |
| Daily Loss | Max 2% portfolio loss | Flatten all positions |
| Drawdown | Max 10% from peak | Reduce position sizes 50% |
| Concentration | Max 40% in single sector | Reject order |

### 7. Market Data Provider Layer

**Purpose**: Abstract market data fetching across vendors (Alpaca, Finnhub).

**Location**: `src/marketdata/`

```python
class MarketDataProvider(ABC):
    source_name: str  # "alpaca", "finnhub"

    @abstractmethod
    def fetch_bars(self, symbol, start, end, resolution="1Min") -> pd.DataFrame:
        """Fetch OHLCV bars with standard columns and timezone-naive index."""
```

- `AlpacaProvider`: Wraps alpaca-py SDK
- `FinnhubProvider`: Wraps finnhub-python SDK
- `utils.py`: RateLimiter, fetch_with_retry, normalize_ohlcv

### 8. Trading Buddy (Trade Evaluation Layer)

**Purpose**: Review proposed trades against risk, context, and process checks. Acts as a mentor and risk guardian -- never predicts or generates signals.

**Location**: `src/evaluators/`, `src/orchestrator.py`, `src/trade/`, `src/rules/`, `src/api/trading_buddy.py`

#### Evaluation Flow
```
TradeIntent
     │
     ▼
ContextPackBuilder
(bars, features, regimes, key levels, MTFA)
     │
     ▼
EvaluatorOrchestrator
     │
     ├─► RiskRewardEvaluator (R:R, sizing, stop sanity)
     ├─► ExitPlanEvaluator (stop/target presence)
     ├─► RegimeFitEvaluator (direction vs regime, transition risk)
     ├─► MTFAEvaluator (timeframe alignment)
     ├─► StopPlacementEvaluator (stop vs structure, ATR distance)
     ├─► StructureAwarenessEvaluator (support/resistance proximity)
     └─► VolatilityLiquidityEvaluator (spread, volume, volatility regime)
     │
     ▼
Deduplicate + Score (100 base - penalties)
     │
     ▼
Guardrails (sanitise predictive language)
     │
     ▼
EvaluationResult (score, items, summary)
```

#### Key Components
- **TradeIntent** (`src/trade/intent.py`): Proposed trade with entry, stop, target, size
- **EvaluationResult** (`src/trade/evaluation.py`): Score + items with severity levels (BLOCKER, CRITICAL, WARNING, INFO)
- **ContextPack** (`src/evaluators/context.py`): Reusable market context with caching (60s TTL)
- **Evaluator** (`src/evaluators/base.py`): ABC with `evaluate(intent, context, config)` returning `list[EvaluationItem]`
- **Registry** (`src/evaluators/registry.py`): `@register_evaluator` decorator for plug-in discovery
- **Guardrails** (`src/rules/guardrails.py`): No-prediction policy enforcement

### 9. Authentication Layer

**Purpose**: Secure API access with Google OAuth and JWT tokens.

**Location**: `src/api/auth.py`, `src/api/auth_middleware.py`

#### Authentication Flow
```
Google Sign-In (Frontend)
         │
         ▼
POST /api/auth/google (ID Token)
         │
         ├─► Verify Google ID Token
         ├─► Find or Create User Account
         ├─► Create User Profile (if new)
         │
         ▼
Return JWT Access Token
         │
         ▼
Subsequent Requests: Authorization: Bearer <JWT>
         │
         ▼
get_current_user() Middleware (validates JWT)
```

- Dev mode bypass via `AUTH_DEV_MODE=true` (returns user_id=1)
- JWT expiration configurable via `AUTH_JWT_EXPIRY_HOURS`
- Google OAuth client ID via `AUTH_GOOGLE_CLIENT_ID`

### 10. Behavioral Checks Engine

**Purpose**: Run behavioral checks against trades at the point of execution. Produces pass/fail results with nudge text that persist to `campaign_checks`.

**Location**: `src/checks/`

- `base.py`: BaseCheck ABC for individual check implementations
- `risk_sanity.py`: Risk sanity checks (position sizing, stop distance, overtrading)
- `runner.py`: CheckRunner that executes all registered checks against a decision context

### 11. Reviewer Service

**Purpose**: Event-driven service that subscribes to review events on the message bus and runs behavioral checks against position campaigns.

**Location**: `src/reviewer/`

- `main.py`: Standalone entry point (runs as a separate process)
- `orchestrator.py`: Event subscriber and check dispatcher
- `publisher.py`: Review event publishing helpers
- `checks/`: Individual check implementations
  - `base.py`: BaseCheck ABC
  - `risk_sanity.py`: Risk sanity checks (position sizing, stop distance, overtrading)
  - `entry_quality.py`: Entry quality checks (timing, setup quality)
  - `runner.py`: CheckRunner execution engine

Events handled: `REVIEW_LEG_CREATED`, `REVIEW_CAMPAIGNS_POPULATED`, `REVIEW_CONTEXT_UPDATED`, `REVIEW_RISK_PREFS_UPDATED`.

### 12. Go Agent Service

**Purpose**: Manages trading agent lifecycle -- polls for active agents, resolves strategy definitions, runs agent loops, and tracks orders and activity.

**Location**: `agent-service/`

#### Architecture
```
┌─────────────────────────────────────────────────────┐
│                  Agent Service (Go)                    │
│                                                        │
│  ┌──────────────┐    ┌──────────────────────────┐     │
│  │  Orchestrator │    │  Agent Loop (per agent)   │     │
│  │  (polls DB    │───►│  1. Resolve strategy      │     │
│  │   for active  │    │  2. Fetch market data     │     │
│  │   agents)     │    │  3. Compute signals       │     │
│  └──────────────┘    │  4. Risk check            │     │
│                       │  5. Submit orders (Alpaca) │     │
│                       │  6. Log activity           │     │
│                       └──────────────────────────┘     │
│                                                        │
│  Repositories: agent_repo, order_repo,                │
│                activity_repo, strategy_repo            │
└─────────────────────────────────────────────────────┘
```

- Configurable via `AS_*` environment variables
- Strategy resolver compiles JSONB DSL conditions into executable logic
- Uses `version` column on `agent_strategies` for cache invalidation
- Docker Compose service with PostgreSQL dependency

### 13. Trading Agents Management

**Purpose**: Python-side management of trading agent configurations, predefined strategy catalog, and API endpoints.

**Location**: `src/trading_agents/`, `src/api/trading_agents.py`

- **Models** (`models.py`): `AgentStrategy`, `TradingAgent`, `AgentOrder`, `AgentActivityLog` SQLAlchemy models
- **Repository** (`repository.py`): CRUD operations for agents, orders, and activity logs
- **Predefined Strategies** (`predefined.py`): Catalog of predefined strategy definitions with entry/exit conditions
- **API Router** (`trading_agents.py`): REST endpoints for strategy CRUD, agent lifecycle (start/pause/stop), and order/activity queries

### 14. Portal UI

**Purpose**: Full single-page application for the trading copilot platform.

**Location**: `ui/frontend/src/portal/`

**Key sections:**
- **Public pages**: Landing, FAQ, How It Works, Pricing, legal (Terms, Privacy, Disclaimer)
- **Auth**: Google OAuth login flow
- **App pages**: Dashboard, Campaigns (with detail view), Investigate/Insights, Journal, Agents (with detail view), Strategy Probe, Evaluate
- **Settings**: Profile, Risk preferences, Strategies (with condition builder), Brokers, Data & Privacy
- **Help**: Evaluations explained, Behavioral Signals, Why Flags, Common Misunderstandings

**Component highlights:**
- ECharts-based analytics (equity curve, drawdown, return distribution, rolling Sharpe, time-of-day heatmap)
- Campaign timeline with checks summary, context panel, and emotion chips
- Trade investigation with filter bar, driver cards, subset metrics, and compare toggle
- Strategy condition builder with grouped select and condition DSL
- Agent management with status badges, order tables, and activity logs

## Data Flow Diagrams

### Training Flow
```
Historical Data (Database/Alpaca)
         │
         ▼
    Feature Pipeline (per timeframe τ)
         │
         ▼
    Train/Val/Test Split (time-based)
         │
         ▼
    Scaler (fit on train only)
         │
         ▼
    Encoder (PCA or Temporal AE)
         │
         ▼
    Latent States z_t
         │
         ▼
    Gaussian HMM (fit on train)
         │
         ▼
    Tune K via AIC/BIC on validation
         │
         ▼
    State Label Alignment (Hungarian matching)
         │
         ▼
    Validation Report (dwell times, transitions, OOD)
         │
         ▼
    Package Artifacts (scaler, encoder, hmm, metadata)
```

### Inference Flow
```
New Bar Close (timeframe τ)
         │
         ▼
    Compute Features x_t
         │
         ▼
    Scale: x̃_t = scaler(x_t)
         │
         ▼
    Encode: z_t = encoder(x̃_t) or encoder(x̃_{t-L:t})
         │
         ▼
    HMM Filtering Update → α_t(k)
         │
         ▼
    Anti-Chatter Check (p_switch, min_dwell)
         │
         ▼
    OOD Check (log p(z_t) threshold)
         │
         ├─► state_id = argmax_k α_t(k)
         └─► state_prob = max(α_t)
         │
         ▼
    Strategy (regime-gated signals)
         │
         ▼
    Risk Manager
         │
         ▼
    Order Manager → Alpaca
```

### Multi-Timeframe Synchronization
```
1Min bar close → compute 1Min state
               │
15Min bar close → compute 15Min state (every 15 bars)
               │
1Hour bar close → compute 1Hour state
               │
1Day bar close → compute 1Day state

Higher TF states carry forward until next update.
```

Supported timeframes: **1Min, 15Min, 1Hour, 1Day** only.

## Configuration Architecture

### Environment Variables (.env)
```bash
# Credentials (never in code)
ALPACA_API_KEY=xxx
ALPACA_SECRET_KEY=xxx
ALPACA_PAPER=true

# Environment
ENVIRONMENT=development  # development, paper, production
LOG_LEVEL=INFO
```

### Pydantic Settings (config/settings.py)
```python
class Settings(BaseSettings):
    finnhub: FinnhubConfig
    alpaca: AlpacaConfig
    data: DataConfig
    features: FeatureConfig
    state: StateConfig
    strategy: StrategyConfig
    backtest: BacktestConfig
    logging: LoggingConfig
    database: DatabaseConfig
```

### YAML Configuration (config/trading.yaml)
```yaml
# Complex/nested configuration
feature_sets:
  default: [log_return_5m, momentum_20, realized_vol_30, ...]

autoencoder:
  architecture: conv1d
  hidden_dims: [32, 64, 128]
  latent_dim: 16

backtest:
  initial_capital: 100000
  commission_per_share: 0.005
```

## Error Handling Strategy

### Exception Hierarchy
```
AlgomaticError (base)
├── DataLoadError
│   ├── DataNotFoundError
│   └── DataValidationError
├── FeatureComputationError
├── StateModelError
│   ├── ModelNotTrainedError
│   └── InferenceError
├── ExecutionError
│   ├── OrderRejectedError
│   └── ConnectionError
└── RiskLimitExceeded
    ├── PositionLimitError
    └── DrawdownLimitError
```

### Retry Strategy
- API calls: Exponential backoff (1s, 2s, 4s, max 3 retries)
- Connection errors: Reconnect with backoff
- Rate limits: Respect Retry-After header

## Testing Strategy

### Test Pyramid
```
        ┌─────────┐
        │   E2E   │  10% - Paper trading integration
        └────┬────┘
        ┌────┴────┐
        │ Integr. │  30% - Pipeline tests
        └────┬────┘
   ┌─────────┴─────────┐
   │       Unit        │  60% - Component tests
   └───────────────────┘
```

### Key Test Scenarios
1. **Data**: Load CSV, validate schema, handle missing data
2. **Features**: Compute features, verify lookback handling
3. **State**: Train autoencoder, verify reconstruction
4. **Strategy**: Generate signals, verify regime filtering
5. **Execution**: Submit orders (mocked), handle fills

## Deployment Architecture

### Development
- Local Python backend + Docker Compose for infrastructure (postgres, redis, data-service, indicator-engine, marketdata-service)
- `AUTH_DEV_MODE=true` bypasses OAuth (uses user_id=1)
- Backend: `uv run uvicorn ui.backend.api:app --host 0.0.0.0 --port $SERVER_PORT`
- Frontend: `npm run dev` in `ui/frontend/`

### Docker Compose (Full Stack)
```bash
docker compose up -d                    # All services
docker compose --profile tools up -d    # Include pgAdmin
```

### Paper Trading
- Cloud VM (or local always-on machine)
- Alpaca paper trading endpoint
- Structured logging to file
- Daily performance reports

### Production (Future)
- Cloud VM with monitoring
- Alpaca live endpoint
- Alerting (email/Slack)
- Automated failover

## Docker Services

The full stack runs via `docker-compose.yml`:

| Service | Image | Purpose |
|---------|-------|---------|
| `postgres` | postgres:16-alpine | Primary database |
| `redis` | redis:7-alpine | Message bus (reviewer events) and caching |
| `data-service` | Go binary (built from `data-service/Dockerfile`) | gRPC server owning market data tables |
| `indicator-engine` | C++ binary (built from `indicator-engine/Dockerfile`) | High-performance indicator computation |
| `marketdata-service` | Go binary (built from `marketdata-service/Dockerfile`) | Market data fetching (Alpaca) + aggregation |
| `reviewer-service` | Python (built from `Dockerfile`) | Event-driven behavioral checks |
| `agent-service` | Go binary (built from `agent-service/Dockerfile`) | Trading agent lifecycle management |
| `pgadmin` | dpage/pgadmin4 | Database management UI (profile: tools) |

Service dependencies: `data-service` → `postgres`; `indicator-engine` / `marketdata-service` → `data-service` + `redis`; `reviewer-service` → `postgres` + `data-service` + `redis`; `agent-service` → `postgres`.

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language (primary) | Python 3.12+ | Ecosystem, Alpaca SDK |
| Language (data services) | Go 1.24+ | Performance, concurrency for gRPC services |
| Language (indicators) | C++ | High-performance indicator computation |
| Data | pandas, numpy, pyarrow | Standard for financial data |
| Database | PostgreSQL 16, SQLAlchemy, Alembic | Persistent storage with migrations |
| Database (Go) | pgx | High-performance PostgreSQL driver for Go |
| RPC | gRPC, Protocol Buffers | Cross-language market data access |
| ML | scikit-learn | PCA, clustering, preprocessing |
| HMM | hmmlearn | Gaussian HMM for regime tracking |
| TA | TA-Lib, pandas-ta | Technical indicators |
| Validation | pandera | DataFrame schema validation |
| Config | pydantic, pydantic-settings, pyyaml | Type-safe configuration |
| Market Data | alpaca-py, finnhub-python | Multi-provider data fetching |
| Message Bus | Redis | Event-driven reviewer service |
| Web Backend | FastAPI, uvicorn | REST API |
| Web Frontend | React 18, TypeScript, Vite | Visualization UI |
| Charting | TradingView Lightweight Charts, Plotly | Interactive charts |
| HTTP Client | httpx | Async HTTP (agent scheduler) |
| Containerisation | Docker, Docker Compose | Deployment |
| Testing | pytest (Python), go test (Go) | Standard testing frameworks |
