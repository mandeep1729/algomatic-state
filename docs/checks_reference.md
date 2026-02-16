# Trade Checks Reference

Complete reference for all behavioral checks and evaluator checks implemented in Trading Buddy.

---

## Overview

Trading Buddy runs two categories of checks against trades:

1. **Behavioral Checks** (CheckRunner) — Post-execution risk sanity gates that persist to the `campaign_checks` table. These fire when a campaign leg is created and produce pass/fail results with nudge text for the trader.

2. **Evaluator Checks** (Evaluator framework) — Pre-trade and retroactive evaluations that persist to the `trade_evaluations` and `trade_evaluation_items` tables. These analyze market context, structure, and trade quality.

### Severity Levels

| Severity | Behavioral Checks | Evaluator Checks | Meaning |
|----------|-------------------|-------------------|---------|
| info     | info              | INFO              | Informational, no action needed |
| warn     | warn              | WARNING           | Caution advised, review recommended |
| critical | critical          | CRITICAL          | Must be resolved before proceeding |

---

## Behavioral Checks (RS Series)

Source: `src/reviewer/checks/risk_sanity.py`

All checks use `check_type="risk_sanity"`, `check_phase="at_entry"`.
Severities are configurable via `ChecksConfig.severity_overrides`.

### RS001 — No Stop-Loss

| Field | Value |
|-------|-------|
| **Default Severity** | critical |
| **Triggers when** | No TradeIntent linked, or `stop_loss` is None/zero |
| **Passes when** | `stop_loss > 0` |
| **Nudge text** | "No stop-loss defined. Every trade needs a predefined exit." |

### RS002 — Risk % of Account

| Field | Value |
|-------|-------|
| **Default Severity** | warn |
| **Escalated Severity** | critical (when risk > 2x threshold) |
| **Threshold** | `max_risk_per_trade_pct` (default: 2.0%) |
| **Triggers when** | `(total_risk / account_balance) * 100 > threshold` |
| **Passes when** | `risk_pct <= threshold` |
| **Skips when** | No account balance or no position size |

### RS003 — Risk:Reward Ratio

| Field | Value |
|-------|-------|
| **Default Severity** | warn |
| **Escalated Severity** | critical (when R:R < 1.0) |
| **Threshold** | `min_rr_ratio` (default: 1.5) |
| **Triggers when** | `risk_reward_ratio < min_rr_ratio` |
| **Passes when** | `risk_reward_ratio >= min_rr_ratio` |

### RS004 — Stop Distance vs ATR

| Field | Value |
|-------|-------|
| **Default Severity** | warn |
| **Threshold** | `min_stop_atr_multiple` (default: 0.5x ATR) |
| **Triggers when** | `stop_distance / ATR < min_stop_atr_multiple` |
| **Passes when** | `atr_multiple >= min_stop_atr_multiple` |
| **Skips when** | ATR not available |

---

## Evaluator Checks

### Risk & Reward (RR Series)

Source: `src/evaluators/risk_reward.py`

#### RR001 — Low Risk/Reward Ratio

| Field | Value |
|-------|-------|
| **Threshold** | `min_rr_ratio` (default: 2.0) |
| **Triggers when** | `risk_reward_ratio < min_rr_ratio` |
| **Severity tiers** | BLOCKER if R:R < 1.0, CRITICAL if < 75% of min, WARNING otherwise |

#### RR002 — Position Risk Exceeds Limit

| Field | Value |
|-------|-------|
| **Threshold** | `max_risk_per_trade_pct` (default: 2.0%) |
| **Triggers when** | `risk_pct > max_risk_per_trade_pct` |
| **Severity tiers** | BLOCKER if > 2x limit, CRITICAL if > 1.5x, WARNING otherwise |

#### RR003 — Stop Loss Too Tight

| Field | Value |
|-------|-------|
| **Default Severity** | WARNING |
| **Threshold** | `min_stop_atr_multiple` (default: 0.5x ATR) |
| **Triggers when** | `stop_distance / ATR < min_stop_atr_multiple` |

#### RR004 — Stop Loss Too Wide

| Field | Value |
|-------|-------|
| **Default Severity** | WARNING |
| **Threshold** | `max_stop_atr_multiple` (default: 3.0x ATR) |
| **Triggers when** | `stop_distance / ATR > max_stop_atr_multiple` |

#### RR005 — Position Size Too Large

| Field | Value |
|-------|-------|
| **Threshold** | `max_position_size_pct` (default: 10.0%) |
| **Triggers when** | `position_value / account_balance * 100 > max_position_size_pct` |
| **Severity tiers** | CRITICAL if > 1.5x limit, WARNING otherwise |

---

### Exit Plan (EP Series)

Source: `src/evaluators/exit_plan.py`

#### EP001 — Missing Stop Loss

| Field | Value |
|-------|-------|
| **Default Severity** | BLOCKER |
| **Triggers when** | `stop_loss <= 0` |

#### EP002 — Missing Profit Target

| Field | Value |
|-------|-------|
| **Default Severity** | WARNING |
| **Triggers when** | `profit_target <= 0` |

#### EP003 — Stop Loss Extremely Close to Entry

| Field | Value |
|-------|-------|
| **Default Severity** | CRITICAL |
| **Threshold** | 0.1% distance from entry (hardcoded) |
| **Triggers when** | `abs(entry - stop) / entry * 100 < 0.1` |

#### EP004 — Profit Target Extremely Close to Entry

| Field | Value |
|-------|-------|
| **Default Severity** | WARNING |
| **Threshold** | 0.1% distance from entry (hardcoded) |
| **Triggers when** | `abs(target - entry) / entry * 100 < 0.1` |

#### EP005 — Stop Near Concerning Key Level

| Field | Value |
|-------|-------|
| **Default Severity** | INFO |
| **Threshold** | `level_proximity_pct` (default: 0.5%) |
| **Triggers when** | Stop is near a level that's concerning for the trade direction |

#### EP006 — Target at Favorable Key Level

| Field | Value |
|-------|-------|
| **Default Severity** | INFO |
| **Threshold** | `level_proximity_pct` (default: 0.5%) |
| **Triggers when** | Target is near a level that's favorable for the trade direction |

---

### Regime Fit (REG Series)

Source: `src/evaluators/regime_fit.py`

#### REG001 — Trade Direction Conflicts with Regime

| Field | Value |
|-------|-------|
| **Default Severity** | WARNING |
| **Triggers when** | LONG + bearish regime, or SHORT + bullish regime |
| **Bullish labels** | up_trending, bullish, trending_up, bull, uptrend, strong_up, momentum_up |
| **Bearish labels** | down_trending, bearish, trending_down, bear, downtrend, strong_down, momentum_down |
| **Skips when** | Regime label is generic (matches `state_N` pattern) |

#### REG002 — High Transition Risk

| Field | Value |
|-------|-------|
| **Default Severity** | WARNING |
| **Threshold** | `transition_risk_threshold` (default: 0.3 / 30%) |
| **Triggers when** | `regime.transition_risk > threshold` |

#### REG003 — High Entropy (Uncertain Regime)

| Field | Value |
|-------|-------|
| **Default Severity** | INFO |
| **Threshold** | `entropy_threshold` (default: 1.5 nats) |
| **Triggers when** | `regime.entropy > threshold` |

#### REG004 — Out-of-Distribution Market Behavior

| Field | Value |
|-------|-------|
| **Default Severity** | WARNING |
| **Triggers when** | `regime.is_ood == True` |

---

### Multi-Timeframe Alignment (MTFA Series)

Source: `src/evaluators/mtfa.py`

#### MTFA001 — Low Timeframe Alignment

| Field | Value |
|-------|-------|
| **Default Severity** | WARNING |
| **Threshold** | `low_alignment_threshold` (default: 0.6 / 60%) |
| **Triggers when** | `alignment_score < threshold` |

#### MTFA002 — High Timeframe Alignment (Positive)

| Field | Value |
|-------|-------|
| **Default Severity** | INFO |
| **Threshold** | `high_alignment_threshold` (default: 0.8 / 80%) |
| **Triggers when** | `alignment_score >= threshold` (confirmation signal) |

#### MTFA003 — HTF Regime Unstable

| Field | Value |
|-------|-------|
| **Default Severity** | WARNING |
| **Threshold** | `htf_transition_risk_threshold` (default: 0.3 / 30%) |
| **HTF timeframes** | 1Hour, 1Day |
| **Triggers when** | Any HTF regime has `transition_risk > threshold` |

---

### Structure Awareness (SA Series)

Source: `src/evaluators/structure_awareness.py`

These checks use **key levels** derived from daily bars:

- **Pivot** = (Prior Day High + Prior Day Low + Prior Day Close) / 3
- **R1** = 2 x Pivot - Prior Day Low
- **R2** = Pivot + (Prior Day High - Prior Day Low)
- **S1** = 2 x Pivot - Prior Day High
- **S2** = Pivot - (Prior Day High - Prior Day Low)
- **Rolling High/Low 20** = Highest high / lowest low over last 20 daily bars
- **VWAP** = Volume-weighted average price for the current session

Key levels are computed in `ContextPackBuilder._build_key_levels()` (`src/evaluators/context.py`).

#### SA001 — Buying Into Resistance

| Field | Value |
|-------|-------|
| **Threshold** | `level_proximity_pct` (default: 0.5%) |
| **Critical threshold** | `level_critical_pct` (default: 0.3%) |
| **Triggers when** | LONG trade entry is within proximity of R1, R2, prior_day_high, or rolling_high_20 |
| **Severity tiers** | CRITICAL if distance <= 0.3%, WARNING if <= 0.5% |

#### SA002 — Shorting Into Support

| Field | Value |
|-------|-------|
| **Threshold** | `level_proximity_pct` (default: 0.5%) |
| **Critical threshold** | `level_critical_pct` (default: 0.3%) |
| **Triggers when** | SHORT trade entry is within proximity of S1, S2, prior_day_low, or rolling_low_20 |
| **Severity tiers** | CRITICAL if distance <= 0.3%, WARNING if <= 0.5% |

#### SA003 — Entry Far From VWAP

| Field | Value |
|-------|-------|
| **Default Severity** | WARNING |
| **Threshold** | `vwap_atr_max` (default: 2.0x ATR) |
| **Triggers when** | Entry price is more than 2.0 ATR away from VWAP |

#### SA004 — Against Higher-Timeframe Trend

| Field | Value |
|-------|-------|
| **Default Severity** | WARNING |
| **Triggers when** | LONG + bearish HTF trend, or SHORT + bullish HTF trend |
| **Uses** | `context.mtfa.htf_trend` label |

---

### Volatility & Liquidity (VL Series)

Source: `src/evaluators/volatility_liquidity.py`

#### VL001 — Low Relative Volume

| Field | Value |
|-------|-------|
| **Default Severity** | WARNING |
| **Threshold** | `min_relative_volume` (default: 0.5x) |
| **Feature** | `relvol_60` (volume relative to 60-bar average) |
| **Triggers when** | `relvol_60 < 0.5` |

#### VL002 — Extended Candle Entry

| Field | Value |
|-------|-------|
| **Threshold** | `extended_candle_zscore` (default: 2.0) |
| **Critical threshold** | `extended_candle_critical_zscore` (default: 3.0) |
| **Feature** | `range_z_60` (bar range z-score vs 60-bar average) |
| **Triggers when** | `range_z_60 > 2.0` |
| **Severity tiers** | CRITICAL if z > 3.0, WARNING if z > 2.0 |

---

### Stop Placement (SP Series)

Source: `src/evaluators/stop_placement.py`

#### SP001 — Stop at Obvious Liquidity Level

| Field | Value |
|-------|-------|
| **Default Severity** | WARNING |
| **Threshold** | `stop_level_proximity_pct` (default: 0.3%) |
| **Triggers when** | Stop is within 0.3% of a sweep level |
| **LONG sweep levels** | prior_day_low, rolling_low_20 |
| **SHORT sweep levels** | prior_day_high, rolling_high_20 |

#### SP002 — Stop Too Tight for Recent Range

| Field | Value |
|-------|-------|
| **Default Severity** | WARNING |
| **Threshold** | `min_stop_range_multiple` (default: 0.5x ATR) |
| **Triggers when** | `stop_distance / ATR < 0.5` |

#### SP003 — Stop at Last Candle Extremum

| Field | Value |
|-------|-------|
| **Default Severity** | INFO |
| **Threshold** | `last_candle_proximity_pct` (default: 0.2%) |
| **Triggers when** | Stop is within 0.2% of the last bar's low (LONG) or high (SHORT) |

---

## Configuration

### ChecksConfig (Behavioral Checks)

Defined in `config/settings.py`. Environment prefix: `CHECKS_`.

| Setting | Default | Description |
|---------|---------|-------------|
| `atr_period` | 14 | ATR lookback period |
| `min_rr_ratio` | 1.5 | Minimum risk:reward ratio |
| `max_risk_per_trade_pct` | 2.0 | Max risk as % of account |
| `min_stop_atr_multiple` | 0.5 | Min stop distance in ATR multiples |
| `severity_overrides` | {} | Per-code severity customization (e.g. `{"RS001": "critical"}`) |

### EvaluatorConfig (Evaluator Checks)

Each evaluator accepts an optional `EvaluatorConfig` with:

- `thresholds`: Dict of threshold name to value (overrides defaults)
- `severity_overrides`: Dict of check code to severity (overrides defaults)
- `enabled_checks`: Set of check codes to run (None = all)

---

## Batch Scripts

| Script | Table | Description |
|--------|-------|-------------|
| `scripts/review_legs.py` | `campaign_checks`, `trade_evaluations` | Publishes `REVIEW_CAMPAIGNS_POPULATED` events so the reviewer service runs both behavioral checks (RS001-RS004) and all 7 evaluators |

The script supports `--dry-run`, `--symbol`, and `--account-id` flags. The reviewer service handles idempotent persistence.
