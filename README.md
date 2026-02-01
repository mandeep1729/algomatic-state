# Algomatic State

Algorithmic trading system using HMM-based regime tracking for market state inference and regime-aware trading strategies.

## Overview

Algomatic State implements a multi-timeframe Hidden Markov Model (HMM) approach to market regime tracking. The system learns continuous latent state vectors from engineered features and uses Gaussian HMMs to infer discrete market regimes, enabling regime-aware trading strategies.

### Key Features

- **Multi-Timeframe Support**: Separate models for 1m, 5m, 15m, 1h, and 1d timeframes
- **HMM Regime Tracking**: Gaussian HMM with configurable state counts and covariance types
- **PCA Encoding**: Dimensionality reduction with automatic latent dimension selection
- **Anti-Chatter Controls**: Minimum dwell time, probability thresholds, majority voting
- **OOD Detection**: Log-likelihood based out-of-distribution detection
- **Walk-Forward Validation**: Time-based cross-validation with leakage prevention
- **Production Monitoring**: Drift detection, shadow inference, retraining triggers

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
- `pandas`, `numpy`: Data manipulation
- `scikit-learn`: PCA and preprocessing
- `hmmlearn`: Gaussian HMM implementation
- `scipy`: Statistical transforms
- `pyarrow`: Parquet storage
- `pydantic`: Configuration management
- `SQLAlchemy`: Database ORM

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

## Project Structure

```
algomatic-state/
├── config/
│   ├── settings.py                 # Pydantic configuration
│   └── state_vector_feature_spec.yaml  # Feature and model config
│
├── src/
│   ├── data/                       # Data loading and storage
│   │   ├── loaders/               # CSV, Alpaca, Database loaders
│   │   └── database/              # SQLAlchemy models
│   │
│   ├── features/                   # Feature engineering
│   │   ├── returns.py             # Return-based features
│   │   ├── volatility.py          # Volatility features
│   │   ├── volume.py              # Volume features
│   │   └── pipeline.py            # Feature orchestration
│   │
│   ├── hmm/                        # HMM State Vector Module
│   │   ├── contracts.py           # Data contracts (FeatureVector, HMMOutput, etc.)
│   │   ├── config.py              # Configuration loading
│   │   ├── artifacts.py           # Model artifact management
│   │   ├── scalers.py             # Robust, Standard, Yeo-Johnson scalers
│   │   ├── encoders.py            # PCA and Temporal PCA encoders
│   │   ├── hmm_model.py           # Gaussian HMM wrapper
│   │   ├── data_pipeline.py       # Feature loading, gap handling, splitting
│   │   ├── training.py            # Training pipeline and hyperparameter tuning
│   │   ├── inference.py           # Online inference engine
│   │   ├── storage.py             # Parquet state storage
│   │   ├── validation.py          # Model validation and diagnostics
│   │   └── monitoring.py          # Drift detection and operations
│   │
│   ├── backtest/                   # Backtesting engine
│   └── execution/                  # Live trading execution
│
├── tests/
│   └── unit/
│       └── hmm/                    # HMM module tests
│
├── models/                         # Trained model artifacts
│   └── timeframe=1Min/
│       └── model_id=state_v001/
│           ├── scaler.pkl
│           ├── encoder.pkl
│           ├── hmm.pkl
│           └── metadata.json
│
├── states/                         # State time-series (Parquet)
│   └── timeframe=1Min/
│       └── model_id=state_v001/
│           └── symbol=AAPL/
│               └── date=2024-01-15/
│                   └── data.parquet
│
└── docs/                           # Documentation
    ├── ARCHITECTURE.md
    └── STATE_VECTOR_HMM_IMPLEMENTATION_PLAN.md
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
# Run all HMM tests
pytest tests/unit/hmm/ -v

# Run with coverage
pytest tests/unit/hmm/ --cov=src/hmm --cov-report=html
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md): System design and data flow
- [Implementation Plan](docs/STATE_VECTOR_HMM_IMPLEMENTATION_PLAN.md): Phase-by-phase implementation details
- [Technical Design](docs/MULTI_TIMEFRAME_STATE_VECTORS_HMM_REGIME_TRACKING.md): HMM design document

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Make your changes following PEP 8 style
4. Write tests for new functionality
5. Commit with meaningful messages
6. Push and create a Pull Request
