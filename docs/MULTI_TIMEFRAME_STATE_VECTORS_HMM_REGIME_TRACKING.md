# Technical Design: Multi‑Timeframe State Vectors + HMM Regime Tracking

## 1. Goals
- Learn **state vectors** (continuous latent representations) from engineered market features.
- Use a **Hidden Markov Model (HMM)** to infer **discrete regimes/states** and their transition dynamics.
- Run the same pipeline at multiple timeframes: **1m, 5m, 15m, 1h, 1d**.
- Support both **offline/backtest** and **online/live** inference with strong controls for **leakage**, **drift**, **state flicker**, and **out-of-distribution (OOD)** conditions.

## 2. Definitions
- **Bar timeframe**: A fixed aggregation interval (1m/5m/15m/1h/1d).
- **Feature vector**: \(x_t \in \mathbb{R}^D\) computed at bar close \(t\).
- **Latent state vector**: \(z_t \in \mathbb{R}^d\) produced by an encoder from \(x_t\) or a rolling window \(x_{t-L:t}\).
- **HMM discrete regime**: \(s_t \in \{1..K\}\) inferred from \(z_{1:t}\).

## 3. Architecture Overview
For each timeframe \(\tau\):

1. **Data** → 2. **Features** \(x_t^{(\tau)}\) → 3. **Scaler** → 4. **Encoder** → \(z_t^{(\tau)}\) → 5. **HMM** → \(p(s_t|z_{1:t})\), \(\hat{s}_t\)

Artifacts are trained per timeframe and versioned:
- `scaler` (fit on train only)
- `encoder` (support PCA and temporal AE/DAE)
- `hmm` (emissions + transitions)
- `feature_spec` + `metadata`

## 4. Data & Bar Construction
### 4.1 Data inputs
- OHLCV bars per symbol (or computed from ticks).
- features in the computed_features table.

### 4.2 Bar alignment rules
- Missing bars: forward-fill *only* for non-price metadata; for OHLCV, mark gaps and optionally drop affected windows.

## 5. Feature Engineering (per timeframe)
### 5.1 Feature families (examples)
- use config/features.json

### 5.2 Normalization considerations
- Use **robust scaling** where heavy tails matter (median/IQR), otherwise standard scaling.
- Scaling is fit per timeframe and typically per training universe.
- Avoid leakage: scaler fits only on the training window.

### 5.3 Feature spec
Maintain `config/state_vector_feature_spec.yaml` per timeframe model:
- names, formulas, window sizes
- required raw fields
- missing data policy
- scaling policy

## 6. State Vector Learning (Encoder)
### 6.1 Recommended baseline: PCA
- Fast, stable, strong baseline.
- \(z_t = W^T (\tilde{x}_t)\), where \(\tilde{x}_t\) is scaled.

### 6.2 Recommended production: Temporal Denoising Autoencoder (optional)
- Encoder consumes a window \(X_t = [\tilde{x}_{t-L+1},...,\tilde{x}_t]\) to produce \(z_t\).
- Denoising objective improves stability (reduces sensitivity to noisy features).
- Keep latent dimension small: \(d\in[6,16]\) typical.

### 6.3 Latent stability note
Axes of neural latents can rotate across retrains. Treat \(z_t\) as a **coordinate system that may drift**, while HMM regimes provide stable discrete semantics.

## 7. HMM Design (Core Requirement)
### 7.1 Model form
Use an HMM over latent vectors \(z_t\):
- Hidden state \(s_t \in \{1..K\}\)
- Emission model \(p(z_t | s_t)\)
- Transition model \(p(s_t | s_{t-1})\)

### 7.2 Emissions
- use **Gaussian HMM** (each state has mean \(\mu_k\) and covariance \(\Sigma_k\))

### 7.3 State count \(K\)
Per timeframe, choose \(K\) via:
- AIC/BIC (fit on validation)
- stability of inferred regimes (dwell times)
- economic interpretability (risk/trend separation)

Typical starting points:
- 1m: K=8–16
- 5m/15m: K=6–12
- 1h: K=4–10
- 1d: K=3–8

### 7.4 Persistence & “flicker” control
HMM already encourages persistence via transitions. Reinforce with:
- initialization bias toward staying in same state
- minimum dwell-time rule in *decision layer* (optional)

### 7.5 Outputs to use
- **Filtered posterior**: \(\alpha_t(k) = p(s_t=k | z_{1:t})\) for live trading.
- **Viterbi path**: \(\hat{s}_{1:T}\) for offline analysis/backtests.

## 8. Training Procedure (per timeframe)
### 8.1 Train/validation/test splits
- Use **time-based splits** (walk-forward). Example:
  - Train: 2019–2023
  - Validate: 2024
  - Test: 2025
- For live systems: rolling windows (e.g., last 12–36 months) and periodic retrain.

### 8.2 Training steps
1. Build bars at timeframe \(\tau\).
2. Compute features \(x_t^{(\tau)}\) using past-only rolling windows.
3. Fit scaler on train, transform train/val/test.
4. Fit encoder on train (PCA or temporal AE). Produce \(z_t\).
5. Fit HMM on \(z_t\) (train only). Tune \(K\) and covariance regularization via validation.
6. Evaluate stability + economic meaning (Section 11).
7. Package artifacts + metadata (Section 10).

### 8.3 Regularization & numerical stability
- Covariance regularization (floor on eigenvalues, diagonal loading).
- Limit covariance structure if needed:
  - diagonal covariance (more stable)
  - tied covariance across states (more stable, less flexible)

### 8.4 Label alignment across retrains
HMM state labels are arbitrary. After retraining:
- match new states to old using distance between \(\mu_k\) and transition structure (Hungarian matching)
- store mapping in metadata so “State 3” keeps meaning.

## 9. Online/Live Inference Logic (per timeframe)
### 9.1 Required runtime inputs
- latest bar(s) for timeframe \(\tau\)
- rolling feature windows (for volatility/trend features)
- rolling encoder window (if temporal encoder)

### 9.2 Inference steps
At each new bar close \(t\):
1. Compute \(x_t\)
2. Scale: \(\tilde{x}_t = scaler(x_t)\)
3. Encode: \(z_t = encoder(\tilde{x}_{t-L:t})\) or \(encoder(\tilde{x}_t)\)
4. HMM filtering update to obtain \(\alpha_t(k)\)
5. Emit:
   - `state_id = argmax_k alpha_t(k)`
   - `state_prob = max(alpha_t)`

### 9.3 Decision-layer anti-chatter (optional)
Even with HMM, add guardrails:
- Only switch if new state prob > `p_switch` (e.g., 0.55–0.7)
- Minimum dwell time `min_dwell_bars`
- Majority vote over last N inferred states (small N)

### 9.4 OOD handling
Compute OOD score using emission likelihood:
- \(\log p(z_t)\) under the HMM mixture
If below threshold:
- label `state_id = UNKNOWN`
- reduce size, widen stops, or disable trading
Log and monitor OOD frequency.

## 10. Storage, Versioning, and Data Model
### 10.1 Model artifacts (immutable)
Per timeframe and model version:
```
models/
  timeframe=1m/model_id=state_v003/
    scaler.pkl
    encoder.onnx (or .pt)
    hmm.pkl
    feature_spec.yaml
    metadata.json
```

### 10.2 State time-series dataset
Store outputs per symbol/date as Parquet, partitioned by timeframe and model_id:
Fields:
- `symbol`, `ts`, `timeframe`, `model_id`
- `z_0..z_{d-1}` (float)
- `state_id` (int)
- `state_prob` (float)
- `loglik` (float)
- optional: `recon_err`, `flags`

Recommended layout:
```
states/timeframe=1m/model_id=state_v003/symbol=AAPL/date=YYYY-MM-DD/*.parquet
```

### 10.3 Why store both z and state_id
- `z_t` supports richer diagnostics and future models.
- `state_id` is stable for strategy rules and reporting.

## 11. Validation Criteria (per timeframe)
### 11.1 Statistical checks
- State dwell time distribution (avoid 1–2 bar regimes unless expected at 1m).
- Transition matrix sanity (diagonal dominance, plausible transitions).
- Posterior confidence distribution (avoid always-uncertain regimes).
- OOD rate (should be low; spikes during major events are acceptable).

### 11.2 Economic meaning
For each state:
- average next-N return (directionality)
- realized volatility / drawdowns
- hit rate, payoff ratio under your momentum rules
- costs/turnover sensitivity

### 11.3 Walk-forward performance
Run three variants:
1) Baseline strategy (no state)
2) State gating (trade only in selected states)
3) State sizing / stop policy by state
Compare out-of-sample Sharpe/Sortino, max DD, tail loss, turnover.

## 12. Multi-Timeframe Handling
### 12.1 Separate models per timeframe
Train separate `model_id` per timeframe because:
- feature windows differ
- regimes differ across horizons
- HMM transition dynamics differ

### 12.2 Synchronization
At execution time (e.g., trading on 1m):
- compute 1m state each minute
- compute 5m/15m/1h/1d states when those bars close
- carry-forward the most recent higher-timeframe state until next update

### 12.3 Hierarchical usage pattern (recommended)
- Higher timeframe states (1h/1d): **risk-on/off filter** + position sizing
- Mid timeframe (15m/5m): **trend quality / chop filter**
- Low timeframe (1m): **entry timing / stop logic**

## 13. Retraining and Operations
### 13.1 Retraining cadence (suggested)
- 1m: weekly or bi-weekly (if microstructure features), otherwise monthly
- 5m/15m: monthly
- 1h/1d: quarterly (unless major drift)

### 13.2 Monitoring
- posterior entropy trend (uncertainty)
- OOD likelihood trend
- regime occupancy drift
- state-conditioned strategy KPIs

### 13.3 Rollout policy
- Train candidate model in parallel
- Backtest walk-forward
- Shadow-run live inference
- Switch model_id only after stability checks

## 14. Implementation Notes
- Prefer diagonal or tied covariance early for stability.
- Consider HMM initialization from k-means on \(z_t\) to speed convergence.
- Keep a strict contract between:
  - `feature_spec` (what x is)
  - `encoder` (how z is computed)
  - `hmm` (how state is inferred)

## 15. Deliverables
For each timeframe \(\tau\):
- `feature_spec.yaml`
- `scaler` + `encoder` + `hmm` artifacts
- `metadata.json` (training window, K, d, universe)
- `states` Parquet dataset with z/state_id/prob/loglik
- validation report (dwell times, transitions, OOD, state-conditioned performance)

