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
├── src/                        # Source code
│   ├── __init__.py
│   │
│   ├── agent/                  # Standalone trading agents
│   │   ├── main.py             # Momentum agent entry point (FastAPI + scheduler)
│   │   ├── config.py           # AgentConfig (AGENT_ env prefix)
│   │   ├── strategy.py         # MomentumStrategy
│   │   ├── scheduler.py        # Async fetch-compute-trade loop
│   │   ├── api.py              # Internal /market-data endpoint
│   │   ├── breakout_main.py    # Breakout agent entry point
│   │   ├── breakout_config.py  # Breakout agent configuration
│   │   ├── breakout_strategy.py # Breakout trading strategy
│   │   ├── contrarian_main.py  # Contrarian agent entry point
│   │   ├── contrarian_config.py # Contrarian agent configuration
│   │   ├── contrarian_strategy.py # Contrarian trading strategy
│   │   ├── vwap_main.py        # VWAP agent entry point
│   │   ├── vwap_config.py      # VWAP agent configuration
│   │   └── vwap_strategy.py    # VWAP trading strategy
│   │
│   ├── api/                    # Public API routers
│   │   ├── trading_buddy.py    # Trading Buddy REST endpoints
│   │   ├── broker.py           # SnapTrade broker integration routes
│   │   ├── alpaca.py           # Direct Alpaca trade sync endpoints
│   │   ├── campaigns.py        # Position campaigns and P&L endpoints
│   │   ├── auth.py             # Google OAuth authentication endpoints
│   │   ├── auth_middleware.py  # JWT token validation middleware
│   │   └── user_profile.py     # User profile and risk preference endpoints
│   │
│   ├── data/                   # Data layer
│   │   ├── __init__.py
│   │   ├── loaders/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # Abstract loader interface
│   │   │   ├── csv_loader.py   # Local CSV files
│   │   │   ├── database_loader.py # PostgreSQL database
│   │   │   ├── alpaca_loader.py # Alpaca API
│   │   │   └── multi_asset.py  # Multi-asset loading with timestamp alignment
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── connection.py   # Database connection and session management
│   │   │   ├── models.py       # Core models (Ticker, OHLCVBar, DataSyncLog, ComputedFeature)
│   │   │   ├── broker_models.py # Broker integration (BrokerConnection, TradeFill, SnapTradeUser)
│   │   │   ├── trading_buddy_models.py # Trading Buddy (UserAccount, TradeIntent, etc.)
│   │   │   ├── strategy_models.py # User-defined trading strategies
│   │   │   ├── trade_lifecycle_models.py # Position lots, campaigns, legs, decision contexts
│   │   │   ├── market_repository.py   # Market data access layer
│   │   │   └── trading_repository.py  # Trading Buddy data access layer
│   │   ├── cache.py            # Data caching
│   │   ├── schemas.py          # Pandera OHLCV schema validation
│   │   └── quality.py          # Data quality checks
│   │
│   ├── messaging/              # In-memory pub/sub message bus
│   │   ├── __init__.py
│   │   ├── events.py           # Event, EventType (REQUEST/UPDATED/FAILED)
│   │   └── bus.py              # MessageBus, get_message_bus singleton
│   │
│   ├── marketdata/             # Market data provider abstraction
│   │   ├── __init__.py
│   │   ├── base.py             # MarketDataProvider ABC
│   │   ├── alpaca_provider.py  # Alpaca data provider
│   │   ├── finnhub_provider.py # Finnhub data provider
│   │   ├── service.py          # MarketDataService (ensure_data, gap detection)
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
│   │   └── mtfa.py             # Multi-timeframe alignment evaluator
│   │
│   ├── orchestrator.py         # EvaluatorOrchestrator (sequential/parallel execution, scoring)
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
├── tests/                      # Test suite
│   ├── conftest.py             # Shared fixtures
│   └── unit/
│       ├── backtest/           # Backtest tests
│       ├── broker/             # Broker integration tests
│       ├── data/               # Data layer tests
│       ├── evaluators/         # Evaluator tests
│       ├── execution/          # Execution tests
│       ├── features/           # Feature tests
│       └── hmm/                # HMM module tests
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
│       └── 010_strategies_first_class.py
│
├── ui/                         # Web UI
│   ├── backend/
│   │   └── api.py              # FastAPI backend
│   ├── frontend/               # React + TypeScript frontend
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
├── Dockerfile                  # Docker image for trading agents
├── docker-compose.yml          # PostgreSQL + pgAdmin services
├── docker-compose.agents.yml   # Trading agent services (momentum, breakout, contrarian, vwap)
│
├── go-strats/                  # Go strategy backtesting framework
│   ├── cmd/                    # CLI entry points
│   └── pkg/                    # Core packages (api, backend, conditions, engine, etc.)
│
├── indicator-engine/           # High-performance C++ indicator computation engine
│   ├── src/                    # Source files (indicators, pipeline, service)
│   └── tests/                  # Unit tests
│
├── proposed-ui/                # Proposed React UI for Position Campaigns
│   └── src/                    # React components with mock data
│
└── docs/                       # Documentation
    ├── ARCHITECTURE.md         # System design and data flow
    ├── APIs.md                 # REST API reference
    ├── DATABASE.md             # Database schema and migrations
    ├── FEATURE.md              # Feature engineering specification
    ├── PRD.md                  # Product requirements document
    ├── PITFALLS.md             # ML and trading pitfalls research
    ├── STRATEGIES_REPO.md      # 100 TA-Lib based trading strategies
    └── archive/                # Historical design documents
        ├── STATE_VECTOR_HMM_IMPLEMENTATION_PLAN.md
        ├── Trading_Buddy_Master_Roadmap_and_DB_Schema.md
        ├── Trading_Buddy_Detailed_TODOs.md
        ├── tradingbuddy_trade_schema.md
        ├── position_campaigns_ui_schema_plan.md
        └── strategy_service_design.md
```

## Core Components

### 1. Data Layer

**Purpose**: Load, validate, and cache OHLCV market data from multiple sources.

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
| Returns | log_return_1m, log_return_5m, momentum_20, roc_10 | Price change measures |
| Volatility | realized_vol_30, atr_14, garman_klass_vol | Price dispersion measures |
| Volume | volume_ma_ratio, obv, vwap_deviation | Trading activity measures |
| Structure | high_low_range, close_position, gap | Bar shape and pattern measures |

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
- Separate models per timeframe: 1m, 5m, 15m, 1h, 1d
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
     └─► MTFAEvaluator (timeframe alignment)
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

### 9. Standalone Momentum Agent

**Purpose**: Dockerised trading agent that runs a fetch-compute-trade loop on a timer.

**Location**: `src/agent/`

#### Agent Architecture
```
┌─────────────────────────────────────────────────┐
│                  Agent Process                    │
│                                                   │
│  ┌───────────────────┐  ┌─────────────────────┐  │
│  │  FastAPI Thread    │  │  Scheduler Loop     │  │
│  │  (internal API)    │  │  (async main loop)  │  │
│  │  /health           │  │                     │  │
│  │  /market-data      │  │  1. Market open?    │  │
│  └───────────────────┘  │  2. Fetch OHLCV     │  │
│                          │  3. Compute features │  │
│                          │  4. Generate signals │  │
│                          │  5. Risk check       │  │
│                          │  6. Submit orders    │  │
│                          └─────────────────────┘  │
└─────────────────────────────────────────────────┘
```

- Configurable via `AGENT_*` environment variables
- Data provider switchable: Alpaca or Finnhub
- Uses `MomentumStrategy` with configurable thresholds
- Docker Compose service with PostgreSQL dependency

### 10. Additional Trading Strategies

**Purpose**: Alternative trading strategies beyond basic momentum, each with its own entry/exit logic.

**Location**: `src/agent/` (strategy-specific files)

#### Available Strategies

| Strategy | Entry Point | Feature | Logic |
|----------|-------------|---------|-------|
| Momentum | `main.py` | `r5` | Long when momentum > threshold, short when < negative threshold |
| Contrarian | `contrarian_main.py` | `r5` | Opposite of momentum: long on negative momentum, short on positive |
| Breakout | `breakout_main.py` | `breakout_20` | Long on breakouts above 20-bar high, short on breakdowns |
| VWAP | `vwap_main.py` | `dist_vwap_60` | Mean reversion: long below VWAP, short above VWAP |

Each strategy follows the same architecture as the momentum agent (FastAPI + scheduler loop) but uses different signal generation logic. All strategies are configured via environment variables with strategy-specific prefixes.

### 11. Authentication Layer

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
1m bar close → compute 1m state
              │
5m bar close → compute 5m state (every 5 bars)
              │
15m bar close → compute 15m state (every 15 bars)
              │
1h bar close → compute 1h state
              │
1d bar close → compute 1d state

Higher TF states carry forward until next update.
```

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
- Local Python environment
- SQLite for caching
- File-based logging

### Paper Trading
- Cloud VM (or local always-on machine)
- Alpaca paper trading endpoint
- Structured logging to file
- Daily performance reports

### Production (Future)
- Cloud VM with monitoring
- Alpaca live endpoint
- Alerting (email/Slack)
- Database for trade history
- Automated failover

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.12+ | Ecosystem, Alpaca SDK |
| Data | pandas, numpy, pyarrow | Standard for financial data |
| Database | PostgreSQL 16, SQLAlchemy, Alembic | Persistent storage with migrations |
| ML | scikit-learn | PCA, clustering, preprocessing |
| HMM | hmmlearn | Gaussian HMM for regime tracking |
| TA | TA-Lib, pandas-ta | Technical indicators |
| Validation | pandera | DataFrame schema validation |
| Config | pydantic, pydantic-settings, pyyaml | Type-safe configuration |
| Market Data | alpaca-py, finnhub-python | Multi-provider data fetching |
| Web Backend | FastAPI, uvicorn | REST API |
| Web Frontend | React 18, TypeScript, Vite | Visualization UI |
| Charting | TradingView Lightweight Charts, Plotly | Interactive charts |
| HTTP Client | httpx | Async HTTP (agent scheduler) |
| Containerisation | Docker, Docker Compose | Deployment |
| Testing | pytest | Standard Python testing |
