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
│  │   Alpaca    │    │    CSV      │    │   Cache     │       │
│  │   Loader    │    │   Loader    │    │   Layer     │       │
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
│  │ Returns │ │Volatility│ │ Volume │ │ Market Structure │     │
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
│         │      Temporal Window Generator       │               │
│         └──────────────────┬──────────────────┘               │
│                            ▼                                  │
│         ┌─────────────────────────────────────┐               │
│         │          Normalizer                  │               │
│         └──────────────────┬──────────────────┘               │
│                            ▼                                  │
│         ┌────────────┬─────┴─────┬────────────┐               │
│         │    PCA     │           │ Autoencoder │               │
│         │  Extractor │           │   (PyTorch) │               │
│         └─────┬──────┘           └──────┬─────┘               │
│               └──────────┬──────────────┘                     │
│                          ▼                                    │
│                   State Validator                             │
│                                                               │
│                      STATE LAYER                              │
└───────────────────────────────┼───────────────────────────────┘
                                │
┌───────────────────────────────┼───────────────────────────────┐
│                               ▼                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │   Regime    │    │   Pattern   │    │  Position   │       │
│  │   Filter    │    │   Matcher   │    │   Sizer     │       │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘       │
│         └──────────────────┼──────────────────┘               │
│                            ▼                                  │
│         ┌─────────────────────────────────────┐               │
│         │    State-Enhanced Momentum Strategy  │               │
│         └──────────────────┬──────────────────┘               │
│                            ▼                                  │
│                    Signal Generator                           │
│                                                               │
│                    STRATEGY LAYER                             │
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
│   ├── trading.yaml            # Strategy parameters
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
│   │   │   └── alpaca_loader.py # Alpaca API
│   │   ├── schemas.py          # Data validation schemas
│   │   ├── cache.py            # Caching layer
│   │   └── validators.py       # Quality checks
│   │
│   ├── features/               # Feature engineering
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract feature interface
│   │   ├── returns.py          # Return-based features
│   │   ├── volatility.py       # Volatility features
│   │   ├── volume.py           # Volume features
│   │   ├── market_structure.py # Structure features
│   │   ├── pipeline.py         # Feature orchestration
│   │   └── registry.py         # Feature registry
│   │
│   ├── windowing/              # Temporal processing
│   │   ├── __init__.py
│   │   ├── temporal.py         # Window generation
│   │   ├── normalization.py    # Normalization methods
│   │   └── dataset.py          # PyTorch Dataset
│   │
│   ├── state/                  # State representation
│   │   ├── __init__.py
│   │   ├── pca.py              # PCA extractor
│   │   ├── autoencoder.py      # PyTorch model
│   │   ├── trainer.py          # Training loop
│   │   ├── state_manager.py    # Orchestration
│   │   └── validation.py       # Quality metrics
│   │
│   ├── strategy/               # Trading logic
│   │   ├── __init__.py
│   │   ├── base.py             # Strategy interface
│   │   ├── momentum.py         # Baseline strategy
│   │   ├── state_enhanced.py   # Enhanced strategy
│   │   ├── regime_filter.py    # Regime filtering
│   │   ├── pattern_matcher.py  # Pattern matching
│   │   ├── position_sizer.py   # Position sizing
│   │   └── signals.py          # Signal types
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
│   │   ├── alpaca_client.py    # Alpaca wrapper
│   │   ├── order_manager.py    # Order lifecycle
│   │   ├── position_tracker.py # Position state
│   │   ├── risk_manager.py     # Risk checks
│   │   ├── paper_trader.py     # Paper trading
│   │   └── live_trader.py      # Live trading
│   │
│   └── utils/                  # Utilities
│       ├── __init__.py
│       ├── logging.py          # Structured logging
│       ├── time_utils.py       # Time/timezone helpers
│       ├── serialization.py    # Model save/load
│       └── exceptions.py       # Custom exceptions
│
├── tests/                      # Test suite
│   ├── conftest.py             # Shared fixtures
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── e2e/                    # End-to-end tests
│
├── scripts/                    # CLI scripts
│   ├── download_data.py
│   ├── train_autoencoder.py
│   ├── run_backtest.py
│   └── run_paper_trading.py
│
├── notebooks/                  # Jupyter notebooks
│   ├── 01_data_exploration.ipynb
│   ├── 02_feature_analysis.ipynb
│   ├── 03_state_representation.ipynb
│   └── 04_strategy_development.ipynb
│
├── data/                       # Data directory
│   ├── raw/                    # Original data files
│   ├── processed/              # Processed datasets
│   └── cache/                  # Cached computations
│
├── models/                     # Trained models
├── logs/                       # Application logs
└── docs/                       # Documentation
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

### 3. State Layer

**Purpose**: Create compressed representations of market conditions.

#### Processing Flow
```
Raw Features (N features)
        │
        ▼
Temporal Windows (window_size × N features)
        │
        ▼
Normalization (z-score per feature)
        │
        ▼
Flattening (window_size × N vector)
        │
        ├─────────────────────────────────┐
        ▼                                 ▼
    PCA (baseline)                  Autoencoder
        │                                 │
        ▼                                 ▼
State Vector (k dims)           State Vector (latent_dim)
```

#### TemporalAutoencoder Architecture
```
Input: (batch, window_size, n_features)
         │
         ▼
    Conv1D(n_features → 32, kernel=3)
    BatchNorm + ReLU
         │
         ▼
    Conv1D(32 → 64, kernel=3)
    BatchNorm + ReLU
         │
         ▼
    Conv1D(64 → 128, kernel=3)
    BatchNorm + ReLU
         │
         ▼
    Flatten + Linear → latent_dim
         │
         ▼
    Latent State: (batch, latent_dim)
         │
         ▼
    Linear + Reshape
         │
         ▼
    ConvTranspose1D (mirror of encoder)
         │
         ▼
Output: (batch, window_size, n_features)
```

#### State Validation Metrics
- **Reconstruction MSE**: How well can we reconstruct the input?
- **Silhouette Score**: How distinct are the learned clusters?
- **Regime Purity**: Do regimes have consistent return distributions?
- **Temporal Stability**: Do states change smoothly over time?

### 4. Strategy Layer

**Purpose**: Generate trading signals from features and states.

#### Signal Flow
```
Market Data
     │
     ├─► Features ─► Momentum Signal (baseline)
     │                      │
     └─► State ────────────►├─► Regime Filter ──► Filtered Signal
                            │         │
                            │         ▼
                            └─► Pattern Match ─► Confidence
                                      │
                                      ▼
                              Position Sizer
                                      │
                                      ▼
                              Final Signal (direction + size)
```

#### Signal Types
```python
@dataclass
class Signal:
    timestamp: datetime
    symbol: str
    direction: Literal["long", "short", "flat"]
    strength: float        # 0.0 to 1.0
    size: float           # Dollar amount or shares
    metadata: dict        # Regime, pattern match info
```

#### Regime-Based Filtering
1. Cluster states using K-means (5-7 regimes)
2. Label regimes by historical momentum performance
3. At inference, classify current state into regime
4. Only trade when regime score exceeds threshold

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
Historical Data (CSV/Alpaca)
         │
         ▼
    Feature Pipeline
         │
         ▼
    Temporal Windowing
         │
         ▼
    Normalization (fit)
         │
    ┌────┴────┐
    ▼         ▼
  PCA      Autoencoder
 (fit)     (train)
    │         │
    └────┬────┘
         ▼
    State Validation
         │
         ▼
    Regime Clustering (fit)
         │
         ▼
    Walk-Forward Backtest
         │
         ▼
    Performance Report
```

### Inference Flow (Live Trading)
```
Alpaca Real-time Data
         │
         ▼
    Feature Pipeline
         │
         ▼
    Temporal Window (latest)
         │
         ▼
    Normalization (transform)
         │
         ▼
    Autoencoder (inference)
         │
         ▼
    Current State
         │
    ┌────┴────┐
    ▼         ▼
 Regime    Pattern
 Filter    Matcher
    │         │
    └────┬────┘
         ▼
    Momentum Strategy
         │
         ▼
    Position Sizer
         │
         ▼
    Risk Manager
         │
         ▼
    Order Manager → Alpaca
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
| ML | PyTorch | Flexibility for custom architectures |
| Validation | pandera | DataFrame schema validation |
| Config | pydantic, pyyaml | Type-safe configuration |
| API | alpaca-py | Official Alpaca SDK |
| Testing | pytest | Standard Python testing |
| Logging | structlog | Structured logging |
| CLI | typer | Modern CLI framework |
