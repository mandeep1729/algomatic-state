# Implementation Plan: Multi-Timeframe State Vectors + HMM Regime Tracking

This document outlines the phased implementation plan for the system described in [MULTI_TIMEFRAME_STATE_VECTORS_HMM_REGIME_TRACKING.md](./MULTI_TIMEFRAME_STATE_VECTORS_HMM_REGIME_TRACKING.md).

---

## Phase 1: Foundation & Configuration

**Goal**: Set up the core infrastructure, configuration system, and data contracts.

| # | Task | Description | Status |
|---|------|-------------|--------|
| 1.1 | Create project structure | Set up `models/`, `states/`, `config/` directories per the spec | [ ] |
| 1.2 | Define `state_vector_feature_spec.yaml` schema | YAML schema for feature names, formulas, window sizes, and **stationarity policy** (diffing/scaling) | [ ] |
| 1.3 | Create `metadata.json` schema | Schema for training window, K, d, universe, version info, and **State TTL** | [ ] |
| 1.4 | Build configuration loader | Load and validate feature specs and model configs per timeframe | [ ] |
| 1.5 | Define data contracts | TypedDict/dataclass for `FeatureVector`, `LatentStateVector`, `HMMOutput` | [ ] |
| 1.6 | Set up artifact versioning | Naming convention and path builder for `models/timeframe=X/model_id=Y/` | [ ] |

---

## Phase 2: Data Pipeline & Feature Loading

**Goal**: Load pre-computed features from database and prepare for state vector training.

| # | Task | Description | Status |
|---|------|-------------|--------|
| 2.1 | Bar alignment & gap handling | Forward-fill logic for non-price data; gap marking for OHLCV | [ ] |
| 2.2 | Feature loader from database | Load features from `computed_features` table per symbol/timeframe | [ ] |
| 2.3 | Feature selection | Select a fixed, curated feature set (listed below) and enforce per-timeframe feature budgets (see 2.8). No automatic inclusion of all candidates. | [ ] |
| 2.4 | Scaler implementation | Robust scaling (median/IQR) and **Yeo-Johnson Power Transforms** for Gaussian alignment | [ ] |
| 2.5 | Train/val/test splitter | Time-based walk-forward splits with configurable windows | [ ] |
| 2.6 | Leakage prevention checks | Validation that scaler fits only on train data | [ ] |
| 2.7 | **Automated Feature Selection** | (Optional) Constrained feature selection within the fixed set: drop redundant/highly collinear features, enforce stability across retrains, and never exceed the feature budget. | [ ] |

### Fixed Feature Set (for State Vector Training)

Use the following features as the **fixed starting set** for training vectors (applies across timeframes unless overridden in config):

- `clv`
- `pullback_depth`
- `r5`
- `r15`
- `r60`
- `vwap_60`
- `dist_vwap_60`
- `tod_sin`
- `macd`
- `stoch_k`
- `sma_20`
- `ema_20`
- `vol_of_vol`
- `vol_z_60`
- `range_1`
- `rv_15`
- `rv_60`
- `relvol_60`
- `range_z_60`
- `bb_middle`
- `bb_width`

Notes:
- Feature budgets (Task **2.8**) still apply per timeframe (you can down-select from this list per TF via config).
- Any automated pruning (Task **2.7**) must operate **within** this list.

---

## Phase 3: State Vector Learning (Encoder)

**Goal**: Implement PCA baseline and optional temporal autoencoder for latent representation.

| # | Task | Description | Status |
|---|------|-------------|--------|
| 3.1 | PCA encoder implementation | `z_t = W^T(x̃_t)` with configurable latent dim d in [6,16] | [ ] |
| 3.2 | Encoder base class | Abstract interface for `fit()`, `transform()`, `save()`, `load()` | [ ] |
| 3.3 | Temporal window encoder | Support for window input `x_{t-L:t}` to `z_t` | [ ] |
| 3.4 | **Temporal Variational Autoencoder (VAE)** | VAE for a continuous, Gaussian latent space (superior alignment for HMM) | [ ] |
| 3.5 | Encoder serialization | Save to `.pkl` or `.onnx` format | [ ] |
| 3.6 | Latent dimension selection | Explained variance analysis for PCA; reconstruction error/KL-divergence for VAE | [ ] |

---

## Phase 4: HMM Regime Model

**Goal**: Implement Gaussian HMM with proper initialization, regularization, and output generation.

| # | Task | Description | Status |
|---|------|-------------|--------|
| 4.1 | Gaussian HMM wrapper | Wrapper around `hmmlearn` with emission model p(z_t\|s_t) | [ ] |
| 4.2 | K-means initialization | Initialize HMM from k-means clustering on z_t | [ ] |
| 4.3 | Covariance regularization | Diagonal loading, eigenvalue floor, tied/diagonal options | [ ] |
| 4.4 | State count selection | AIC/BIC computation on validation set | [ ] |
| 4.5 | Transition matrix initialization | Bias toward diagonal (persistence) | [ ] |
| 4.6 | Filtered posterior computation | alpha_t(k) = p(s_t=k \| z_{1:t}) for live inference | [ ] |
| 4.7 | Viterbi decoding | s_hat_{1:T} for offline/backtest analysis | [ ] |
| 4.8 | HMM serialization | Save/load `.pkl` with metadata | [ ] |

---

## Phase 5: Training Pipeline

**Goal**: End-to-end training workflow per timeframe with proper validation.

| # | Task | Description | Status |
|---|------|-------------|--------|
| 5.1 | Training orchestrator | Coordinate: load features from DB -> scaler -> encoder -> HMM | [ ] |
| 5.2 | Hyperparameter tuning | Grid search for K, latent dim d, covariance type | [ ] |
| 5.3 | Cross-validation framework | Walk-forward validation with multiple folds | [ ] |
| 5.4 | Label alignment (Hungarian matching) | Match new states to old after retrain | [ ] |
| 5.5 | Artifact packaging | Bundle scaler, encoder, hmm, feature_spec, metadata | [ ] |
| 5.6 | Training reproducibility | Seed management, config logging | [ ] |

---

## Phase 6: Online/Live Inference

**Goal**: Real-time inference engine with anti-chatter and OOD detection.

| # | Task | Description | Status |
|---|------|-------------|--------|
| 6.1 | Inference engine class | Load artifacts, process new bars, emit state_id + prob | [ ] |
| 6.2 | Rolling feature buffer | Maintain window state for online feature computation | [ ] |
| 6.3 | HMM filtering update | Incremental alpha_t update at each bar close | [ ] |
| 6.4 | Anti-chatter layer | p_switch threshold, min_dwell_bars, majority vote | [ ] |
| 6.5 | OOD detection | Multi-layer OOD & model health: emission log p(z_t) threshold -> UNKNOWN, plus posterior entropy spikes and state-occupancy collapse detection (see 6.7–6.8). | [ ] |
| 6.6 | Multi-timeframe synchronizer | Carry-forward higher TF states with **Validity TTL** checks | [ ] |

---

## Phase 7: Storage & Data Model

**Goal**: Persist state time-series and support efficient querying.

| # | Task | Description | Status |
|---|------|-------------|--------|
| 7.1 | Parquet writer | Write z_t, state_id, state_prob, loglik per symbol/date | [ ] |
| 7.2 | Partition layout | `states/timeframe=X/model_id=Y/symbol=Z/date=YYYY-MM-DD/` | [ ] |
| 7.3 | Parquet reader | Load state history for backtesting | [ ] |
| 7.4 | Schema validation | Ensure required fields: symbol, ts, timeframe, model_id, z_*, state_id, etc. | [ ] |
| 7.5 | **DB Mirroring (Optional)** | Store latest regime per symbol in `current_states` table for real-time UI/Monitoring | [ ] |

---

## Phase 8: Validation & Diagnostics

**Goal**: Statistical and economic validation of trained models.

| # | Task | Description | Status |
|---|------|-------------|--------|
| 8.1 | Dwell time analysis | Distribution of regime durations per state | [ ] |
| 8.2 | Transition matrix diagnostics | Diagonal dominance, transition sanity checks | [ ] |
| 8.3 | Posterior confidence analysis | Distribution of max(alpha_t) | [ ] |
| 8.4 | OOD rate monitoring | Track OOD frequency over time | [ ] |
| 8.5 | State-conditioned returns | Avg next-N return, volatility, drawdown per state | [ ] |
| 8.6 | Walk-forward backtest | Compare baseline vs state-gated vs state-sized strategies | [ ] |
| 8.7 | Validation report generator | Automated report with all metrics | [ ] |

---

## Phase 9: Operations & Monitoring

**Goal**: Production monitoring, retraining triggers, and rollout procedures.

| # | Task | Description | Status |
|---|------|-------------|--------|
| 9.1 | Monitoring dashboard | Posterior entropy, OOD trend, regime occupancy | [ ] |
| 9.2 | Drift detection | Alert on regime distribution shift | [ ] |
| 9.3 | Shadow inference | Run candidate model in parallel before switch | [ ] |
| 9.4 | Model rollout manager | Switch model_id after stability checks | [ ] |
| 9.5 | Retraining scheduler | Cadence-based (Weekly) plus economic & statistical triggers: reconstruction loss / log-likelihood decay **and** z-scored log-likelihood vs trailing window, KL divergence / PSI on feature and state distributions, entropy spikes, and occupancy collapse alerts. | [ ] |

---


## Failure Modes & Mitigations

| Failure Mode | Common Symptom | Suggested Mitigation |
|---|---|---|
| Feature drift / distribution shift | Emission log-likelihood decays; OOD rate rises; state occupancy collapses | Trigger retrain evaluation; refresh scaling; review feature stability; consider lowering K |
| Regime churn / chatter | Excessive state switching; unstable live signals | Increase min_dwell_bars; raise p_switch; increase diagonal bias in transition matrix; reduce K |
| Silent leakage | Backtest looks unrealistically strong vs live; validation inconsistencies | Hard assertions: scaler fit on train only; strict time splits; unit tests for leakage |
| Latent instability across retrains | State semantics change; Hungarian mapping becomes unstable | Latent anchoring (3.7); freeze reference feature subset; block rollout on drift threshold |
| Data gaps / feed issues | Missing bars; abrupt feature spikes | Gap marking; robust forward-fill policies; quarantine symbol/time window; UNKNOWN state fallback |
| Covariance degeneracy | HMM fails to converge; near-singular covariances | Diagonal loading; eigenvalue floor; use diagonal/tied covariance; shrinkage |

## Phase Dependencies

```
Phase 1 (Foundation)
    |
    v
Phase 2 (Data & Features)
    |
    v
Phase 3 (Encoder)
    |
    v
Phase 4 (HMM)
    |
    v
Phase 5 (Training Pipeline)
    |
    +---> Phase 6 (Live Inference)
    |
    +---> Phase 7 (Storage)
              |
              v
         Phase 8 (Validation)
              |
              v
         Phase 9 (Operations)
```

---

## Suggested Timeframe-Specific Configuration

Based on the design document:

| Timeframe | K (states) | Retrain Cadence | Primary Use |
|-----------|------------|-----------------|-------------|
| 1m | 8-16 | Weekly/Bi-weekly | Entry timing, stop logic |
| 5m | 6-12 | Monthly | Trend quality, chop filter |
| 15m | 6-12 | Monthly | Trend quality, chop filter |
| 1h | 4-10 | Quarterly | Risk-on/off filter, sizing |
| 1d | 3-8 | Quarterly | Risk-on/off filter, sizing |

---

## Notes

- Start with PCA encoder (Phase 3.1) before attempting temporal autoencoder
- Use diagonal covariance in HMM initially for stability
- Prioritize Phases 1-5 for MVP; Phases 6-9 for production readiness
