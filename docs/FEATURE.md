# FEATURE.md
## Base Feature Vector for 1-Minute State Model (Time-of-Day + Momentum-Payoff Aware)

This document specifies a practical, robust base feature set computed from **1-minute OHLCV** data to train a **state / regime representation**. The goal is to:
1) learn a latent **state vector** suitable for regime detection and pattern matching,  
2) align the learned representation with **future momentum payoff** (without leakage), and  
3) make the representation explicitly **time-of-day aware**.

Assumptions:
- No corporate events or stock splits
- Regular Trading Hours (RTH) only (e.g., 09:30–16:00 US/Eastern)
- Features computed causally (using past-only information)

---

## 1. Notation

At minute `t`:
- `O_t, H_t, L_t, C_t, V_t` = open, high, low, close, volume
- `eps` = small constant (e.g., `1e-9`) for numerical stability
- `log()` = natural logarithm

Rolling windows:
- `k ∈ {5, 15, 60}` minutes (configurable)
- Rolling stats must be computed using **past-only** bars.

---

## 2. Feature Groups

### A) Returns & Trend (Momentum Backbone)
These capture direction and persistence at multiple horizons.

1. **r1**  
   `r1_t = log(C_t / C_{t-1})`

2. **r5**  
   `r5_t = log(C_t / C_{t-5})`

3. **r15**  
   `r15_t = log(C_t / C_{t-15})`

4. **r60**  
   `r60_t = log(C_t / C_{t-60})`

5. **cumret_60**  
   `cumret_60_t = sum_{i=t-59..t} r1_i`

6. **ema_diff** (trend proxy; normalized)  
   `ema_diff_t = (EMA_12(C)_t - EMA_48(C)_t) / C_t`

7. **slope_60** (trend slope of log price)  
   Fit linear regression on `log(C)` over the last 60 minutes; slope is the feature.  
   (Optionally normalize slope by price or vol.)

8. **trend_strength**  
   `trend_strength_t = |slope_60_t| / (rv_60_t + eps)`

---

### B) Volatility & Range (Regime + Risk Context)
These help identify chop, transitions, and volatility regimes.

9. **rv_15** (realized vol proxy)  
   `rv_15_t = std(r1_{t-14..t})`

10. **rv_60**  
   `rv_60_t = std(r1_{t-59..t})`

11. **range_1** (normalized range)  
   `range_1_t = (H_t - L_t) / (C_t + eps)`

12. **atr_60** (intraday ATR-like)  
   `atr_60_t = mean(range_1_{t-59..t})`

13. **range_z_60**  
   `range_z_60_t = zscore(range_1_t; window=60)`  
   where zscore uses rolling mean/std over last 60 minutes.

14. **vol_of_vol**  
   `vol_of_vol_t = std(rv_15_{t-59..t})`

---

### C) Volume & Participation (Confirmations)
Participation improves the reliability of momentum continuation.

15. **vol1**  
   `vol1_t = V_t`

16. **dvol1** (dollar volume)  
   `dvol1_t = C_t * V_t`

17. **relvol_60**  
   `relvol_60_t = V_t / (mean(V_{t-59..t}) + eps)`

18. **vol_z_60**  
   `vol_z_60_t = zscore(V_t; window=60)`

19. **dvol_z_60**  
   `dvol_z_60_t = zscore(dvol1_t; window=60)`

---

### D) Intrabar Structure (Microstructure-lite)
These distinguish orderly trends from noisy reversals.

20. **clv** (close location value)  
   `clv_t = (C_t - L_t) / (H_t - L_t + eps)`

21. **body_ratio**  
   `body_ratio_t = |C_t - O_t| / (H_t - L_t + eps)`

22. **upper_wick**  
   `upper_wick_t = (H_t - max(O_t, C_t)) / (H_t - L_t + eps)`

23. **lower_wick**  
   `lower_wick_t = (min(O_t, C_t) - L_t) / (H_t - L_t + eps)`

---

### E) Anchors & Location (Context for Continuation)
These features capture where price is relative to key intraday anchors.

24. **vwap_60** (helper)  
   `vwap_60_t = sum(price_i * volume_i)/sum(volume_i)` over last 60 minutes  
   using `price_i = (H_i + L_i + C_i)/3` or `C_i` (choose one consistently).

25. **dist_vwap_60**  
   `dist_vwap_60_t = (C_t - vwap_60_t) / (C_t + eps)`

26. **dist_ema_48**  
   `dist_ema_48_t = (C_t - EMA_48(C)_t) / (C_t + eps)`

27. **breakout_20**  
   `breakout_20_t = (C_t - rolling_high_20_t) / (C_t + eps)`  
   where `rolling_high_20_t = max(H_{t-19..t})`

28. **pullback_depth**  
   `pullback_depth_t = (rolling_high_20_t - C_t) / (rolling_high_20_t + eps)`

---

### F) Market Context (Recommended)
Compute a small set of aligned features for a benchmark (e.g., SPY or QQQ) at the same minute.

Benchmark features:
- **mkt_r5**, **mkt_r15** (same formulas as returns above)
- **mkt_rv_60**
- **beta_60**: rolling regression of asset `r1` vs market `r1` over 60 minutes
- **resid_rv_60**: std of regression residuals over 60 minutes

These stabilize regime detection and reduce false signals.

---

## 3. Time-of-Day Encoding (Required)

Let:
- `tod` = minutes since market open (0 at 09:30, 390 at 16:00)
- `tod_norm = tod / 390` in `[0,1]`

29. **tod_sin**  
   `tod_sin_t = sin(2π * tod_norm)`

30. **tod_cos**  
   `tod_cos_t = cos(2π * tod_norm)`

Optional session flags (binary):
- **is_open_window**: 1 if `tod < 30`
- **is_midday**: 1 if `120 <= tod <= 240` (example)
- **is_close_window**: 1 if `tod > 330`

Optional but powerful (time-of-day-normalized z-scores; training-only baselines):
- **vol_z_by_tod**: z-score volume vs historical distribution at same minute-of-day
- **range_z_by_tod**: z-score range vs historical distribution at same minute-of-day

---

## 4. Recommended Minimal Starter Set (Lean Build)

If you want a fast first iteration, start with:

Per-asset:
- r1, r5, r15, r60
- rv_60
- range_1, range_z_60
- relvol_60, vol_z_60
- clv, body_ratio
- dist_vwap_60
- breakout_20

Time-of-day:
- tod_sin, tod_cos

Total: ~15–16 features (strong baseline for representation learning).

---

## 5. Windowing Spec (for State Learning)

A single training sample is a window of the above features.

- Lookback length: `L = 60` minutes (configurable)
- Step size: `S = 1` minute (or `S=5` initially)
- Sample tensor: `X_t ∈ R^{L × F}` where `F` is number of features

Use time-based splits:
- Train (earliest time segment)
- Validation (middle)
- Test (latest)

---

## 6. Momentum-Payoff Awareness (Training Target Spec)

To train a state representation aligned to future momentum payoff, define a *payoff label* for each window end time `t`.

### 6.1 Forward Horizon
Choose `H` (e.g., 30 or 60 minutes).

- **fwd_ret_H**  
  `fwd_ret_H_t = log(C_{t+H} / C_t)`

- **fwd_dd_H** (forward drawdown from entry)  
  `fwd_dd_H_t = min_{u ∈ (t, t+H]} log(L_u / C_t)`

- **payoff_score** (risk-adjusted)  
  `payoff_score_t = fwd_ret_H_t - λ * |fwd_dd_H_t|`  
  where `λ` is a risk penalty (e.g., 0.5–2.0).

Convert `payoff_score` to:
- regression target (continuous), or
- 3-class label (bad/neutral/good) using quantiles.

### 6.2 Multi-Task Training (Recommended)
Train an encoder with two objectives:
1) **Reconstruction loss**: autoencoder reconstructs the input window
2) **Payoff head loss**: predicts payoff label from latent state

Total loss:
`L = L_recon + α * L_payoff`

This encourages the latent state to encode information relevant to *future momentum payoff*.

### 6.3 Leakage Control (Critical)
- Use time-based splits
- Use a purge gap at least `H` minutes between train/val/test boundaries
- Ensure normalization uses past-only data

---

## 7. Implementation Notes (Anti-Overfit Guidelines)

- Prefer scale-free features (returns, ratios, z-scores)
- Keep feature set compact at first; add complexity only after validation
- Train across many stocks (shared representation), not a single ticker
- Start latent dimension at 8
- Validate representation stability (no latent collapse, consistent clustering)

---

## 8. Output Contracts

Per minute (per symbol), you should be able to produce:
- `base_features[t]` (feature vector)
- `window_features[t]` (L×F window)
- `state_vector[t] = encoder(window_features[t])` (latent representation)

These are then used to:
- filter momentum trades by regime,
- run similarity / kNN pattern matching,
- dynamically size or adapt exits.

---
