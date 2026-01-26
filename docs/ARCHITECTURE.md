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
│         ┌─────────────────────────────────────┐               │
│         │         Gaussian HMM                │               │
│         │    (Regime Inference + Filtering)   │               │
│         └──────────────────┬──────────────────┘               │
│                            ▼                                  │
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
│   └── assets.yaml             # Asset universe
│
├── src/                        # Source code
│   ├── __init__.py
│   │
│   ├── data/                   # Data layer
│   │   ├── __init__.py
│   │   ├── loaders/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # Abstract loader interface
│   │   │   ├── csv_loader.py   # Local CSV files
│   │   │   ├── database_loader.py # PostgreSQL database
│   │   │   └── alpaca_loader.py # Alpaca API
│   │   └── database/
│   │       ├── __init__.py
│   │       ├── connection.py   # Database connection
│   │       ├── models.py       # SQLAlchemy models
│   │       └── repository.py   # Data access layer
│   │
│   ├── features/               # Feature engineering
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract feature interface
│   │   ├── returns.py          # Return-based features
│   │   ├── volatility.py       # Volatility features
│   │   ├── volume.py           # Volume features
│   │   ├── intrabar.py         # Intrabar features
│   │   ├── time_of_day.py      # Time-based features
│   │   ├── market_context.py   # Market context features
│   │   ├── anchor.py           # Anchor VWAP features
│   │   ├── talib_indicators.py # TA-Lib indicators
│   │   ├── pandas_ta_indicators.py # pandas-ta indicators
│   │   ├── pipeline.py         # Feature orchestration
│   │   └── registry.py         # Feature registry
│   │
│   ├── hmm/                    # HMM State Vector Module
│   │   ├── __init__.py         # Module exports
│   │   ├── contracts.py        # Data contracts (FeatureVector, HMMOutput, etc.)
│   │   ├── config.py           # Configuration loading
│   │   ├── artifacts.py        # Model artifact management
│   │   ├── scalers.py          # Robust, Standard, Yeo-Johnson scalers
│   │   ├── encoders.py         # PCA and Temporal PCA encoders
│   │   ├── hmm_model.py        # Gaussian HMM wrapper
│   │   ├── data_pipeline.py    # Feature loading, gap handling, splitting
│   │   ├── training.py         # Training pipeline and hyperparameter tuning
│   │   ├── inference.py        # Online inference engine
│   │   ├── storage.py          # Parquet state storage
│   │   ├── validation.py       # Model validation and diagnostics
│   │   └── monitoring.py       # Drift detection and operations
│   │
│   ├── strategy/               # Trading logic (uses HMM states)
│   │   └── (regime-gated signal generation)
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
│   │   └── runner.py           # Trading runner
│   │
│   └── utils/                  # Utilities
│       ├── __init__.py
│       ├── logging.py          # Structured logging
│       └── exceptions.py       # Custom exceptions
│
├── tests/                      # Test suite
│   ├── conftest.py             # Shared fixtures
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── e2e/                    # End-to-end tests
│
├── scripts/                    # CLI scripts
│   ├── helpers/                # Shared helper modules
│   │   ├── data.py
│   │   ├── logging_setup.py
│   │   └── output.py
│   ├── download_data.py
│   ├── compute_features.py
│   ├── import_csv_to_db.py
│   ├── init_db.py
│   ├── run_paper_trading.py
│   └── run_live_trading.py
│
├── ui/                         # Web UI
│   ├── backend/
│   │   └── api.py              # FastAPI backend
│   └── frontend/               # React frontend
│
├── data/                       # Data directory (gitignored)
├── models/                     # Trained models (per timeframe)
│   └── timeframe=X/model_id=Y/ # Versioned model artifacts
├── states/                     # State time-series (Parquet)
├── logs/                       # Application logs
└── docs/                       # Documentation
    ├── ARCHITECTURE.md
    ├── STATE_VECTOR_HMM_IMPLEMENTATION_PLAN.md
    └── MULTI_TIMEFRAME_STATE_VECTORS_HMM_REGIME_TRACKING.md
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

**Location**: `src/hmm/`

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

#### Key Components
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
    alpaca: AlpacaSettings
    data: DataSettings
    features: FeatureSettings
    state: StateSettings
    strategy: StrategySettings
    risk: RiskSettings
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
| Language | Python 3.11+ | Ecosystem, Alpaca SDK |
| Data | pandas, numpy, pyarrow | Standard for financial data |
| Database | PostgreSQL, SQLAlchemy | Persistent storage for OHLCV and features |
| ML | PyTorch, scikit-learn | Encoder training, clustering |
| HMM | hmmlearn | Gaussian HMM for regime tracking |
| TA | TA-Lib, pandas-ta | Technical indicators |
| Validation | pandera | DataFrame schema validation |
| Config | pydantic, pyyaml | Type-safe configuration |
| API | alpaca-py | Official Alpaca SDK |
| Web | FastAPI, React | Visualization UI |
| Testing | pytest | Standard Python testing |
| Logging | structlog | Structured logging |
