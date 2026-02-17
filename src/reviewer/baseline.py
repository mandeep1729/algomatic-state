"""Baseline Stats Computation — per-user aggregate trading behavior metrics.

Computes trader baseline attributes per BASELINE.md:
- Holding period profile
- Entry style profile
- Risk profile
- Entry behavior metrics
- Volatility behavior
- Psychological metrics (FOMO index, discipline score)

Results are persisted in user_profiles.stats JSONB via the internal API.
"""

import logging
import statistics
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from src.reviewer.api_client import ReviewerApiClient

logger = logging.getLogger(__name__)

# Default timeframe when none is specified in decision context
_DEFAULT_TIMEFRAME = "15Min"


def compute_baseline_stats(
    account_id: int,
    api_client: ReviewerApiClient,
    lookback_days: int = 90,
    min_fills: int = 5,
) -> Optional[dict]:
    """Compute baseline trading stats for a user from their fill history.

    Flow:
    1. Fetch fills + decision contexts via API
    2. Skip if too few fills
    3. For each fill, fetch OHLCV bars and compute indicators locally
    4. Aggregate all BASELINE.md metrics across fills
    5. Save to user_profiles.stats via API

    Args:
        account_id: User account ID
        api_client: HTTP client for backend API calls
        lookback_days: Days of history to consider
        min_fills: Minimum fills required to compute stats

    Returns:
        Computed stats dict, or None if insufficient data
    """
    logger.info(
        "Computing baseline stats for account_id=%s (lookback=%d days, min_fills=%d)",
        account_id, lookback_days, min_fills,
    )

    # 1. Fetch fills
    fills = api_client.get_fills(account_id, lookback_days)
    if len(fills) < min_fills:
        logger.info(
            "Skipping baseline for account_id=%s: only %d fills (need %d)",
            account_id, len(fills), min_fills,
        )
        return None

    # 2. Fetch profile for account balance
    try:
        profile = api_client.get_profile(account_id)
        account_balance = profile.get("account_balance", 0.0)
    except Exception:
        logger.warning("Could not fetch profile for account_id=%s", account_id, exc_info=True)
        account_balance = 0.0

    # 3. For each fill, compute indicator snapshot
    fill_snapshots = []
    for fill in fills:
        snapshot = _compute_fill_indicators(fill, api_client)
        if snapshot is not None:
            fill_snapshots.append({"fill": fill, "snapshot": snapshot})

    if len(fill_snapshots) < min_fills:
        logger.info(
            "Skipping baseline for account_id=%s: only %d fills with indicators (need %d)",
            account_id, len(fill_snapshots), min_fills,
        )
        return None

    # 4. Aggregate metrics
    stats = _aggregate_metrics(fill_snapshots, account_balance, lookback_days)

    # 5. Save via API
    try:
        api_client.save_baseline_stats(account_id, stats)
        logger.info(
            "Baseline stats saved for account_id=%s: %d fills analyzed",
            account_id, len(fill_snapshots),
        )
    except Exception:
        logger.exception("Failed to save baseline stats for account_id=%s", account_id)

    return stats


def _compute_fill_indicators(fill: dict, api_client: ReviewerApiClient) -> Optional[dict]:
    """Fetch OHLCV bars around a fill and compute indicator snapshot.

    Args:
        fill: Fill dict from API
        api_client: HTTP client

    Returns:
        Dict of indicator values at the fill bar, or None if unavailable
    """
    symbol = fill.get("symbol")
    executed_at = fill.get("executed_at")
    timeframe = fill.get("timeframe") or _DEFAULT_TIMEFRAME

    if not symbol or not executed_at:
        return None

    try:
        bars = api_client.get_ohlcv_bars(
            symbol=symbol,
            timeframe=timeframe,
            end=executed_at,
            last_n_bars=250,
        )

        if not bars or len(bars) < 30:
            logger.debug(
                "Insufficient bars for %s/%s at %s (%d bars)",
                symbol, timeframe, executed_at, len(bars) if bars else 0,
            )
            return None

        df = _bars_to_dataframe(bars)
        snapshot = _compute_indicator_snapshot(df)
        return snapshot

    except Exception:
        logger.debug(
            "Failed to compute indicators for fill %s/%s at %s",
            symbol, timeframe, executed_at, exc_info=True,
        )
        return None


def _bars_to_dataframe(bars: list[dict]) -> pd.DataFrame:
    """Convert bar dicts to OHLCV DataFrame with datetime index."""
    records = []
    for bar in bars:
        records.append({
            "timestamp": pd.Timestamp(bar["timestamp"]),
            "open": float(bar["open"]),
            "high": float(bar["high"]),
            "low": float(bar["low"]),
            "close": float(bar["close"]),
            "volume": float(bar["volume"]),
        })
    df = pd.DataFrame(records)
    df = df.set_index("timestamp").sort_index()
    return df


def _compute_indicator_snapshot(df: pd.DataFrame) -> Optional[dict]:
    """Compute indicators on OHLCV DataFrame and extract last row values.

    Uses TALibIndicatorCalculator, VolatilityFeatureCalculator, and
    AnchorFeatureCalculator from the features package.

    Returns:
        Dict of indicator name → value at the last bar, or None on error
    """
    try:
        from src.features.talib_indicators import TALibIndicatorCalculator, TALIB_AVAILABLE
        from src.features.volatility import VolatilityFeatureCalculator
        from src.features.anchor import AnchorFeatureCalculator

        snapshot = {}

        # TA-Lib indicators
        if TALIB_AVAILABLE:
            talib_calc = TALibIndicatorCalculator()
            talib_df = talib_calc.compute(df)
            if not talib_df.empty:
                last_row = talib_df.iloc[-1]
                for col in talib_df.columns:
                    val = last_row[col]
                    if pd.notna(val):
                        snapshot[col] = float(val)

                # Also capture previous MACD hist for exhaustion detection
                if len(talib_df) >= 2 and "macd_hist" in talib_df.columns:
                    prev_val = talib_df["macd_hist"].iloc[-2]
                    if pd.notna(prev_val):
                        snapshot["macd_hist_prev"] = float(prev_val)

        # Volatility features
        vol_calc = VolatilityFeatureCalculator()
        vol_df = vol_calc.compute(df)
        if not vol_df.empty:
            last_row = vol_df.iloc[-1]
            for col in vol_df.columns:
                val = last_row[col]
                if pd.notna(val):
                    snapshot[col] = float(val)

        # Anchor features
        anchor_calc = AnchorFeatureCalculator()
        anchor_df = anchor_calc.compute(df)
        if not anchor_df.empty:
            last_row = anchor_df.iloc[-1]
            for col in anchor_df.columns:
                val = last_row[col]
                if pd.notna(val):
                    snapshot[col] = float(val)

        # Add volume from original df
        if not df.empty:
            snapshot["volume"] = float(df["volume"].iloc[-1])

        return snapshot if snapshot else None

    except Exception:
        logger.debug("Failed to compute indicator snapshot", exc_info=True)
        return None


def _aggregate_metrics(
    fill_snapshots: list[dict],
    account_balance: float,
    lookback_days: int,
) -> dict:
    """Aggregate all BASELINE.md metrics across fill snapshots.

    Args:
        fill_snapshots: List of {"fill": dict, "snapshot": dict}
        account_balance: User's account balance
        lookback_days: Number of lookback days used

    Returns:
        Complete baseline stats dict
    """
    fills = [fs["fill"] for fs in fill_snapshots]
    snapshots = [fs["snapshot"] for fs in fill_snapshots]

    stats = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "fill_count": len(fills),
    }

    # --- Holding period ---
    stats["holding_period"] = _compute_holding_period(fills)

    # --- Entry style profile ---
    stats["entry_style"] = _compute_entry_style(fills, snapshots)

    # --- Risk profile ---
    stats["risk_profile"] = _compute_risk_profile(fills, snapshots, account_balance)

    # --- Entry behavior ---
    stats["entry_behavior"] = _compute_entry_behavior(fills, snapshots)

    # --- Volatility behavior ---
    stats["volatility_behavior"] = _compute_volatility_behavior(snapshots)

    # --- Psychological metrics ---
    stats["psychological"] = _compute_psychological_metrics(snapshots)

    return stats


def _safe_mean(values: list[float]) -> float:
    """Compute mean, returning 0.0 for empty lists."""
    return statistics.mean(values) if values else 0.0


def _safe_median(values: list[float]) -> float:
    """Compute median, returning 0.0 for empty lists."""
    return statistics.median(values) if values else 0.0


def _safe_stdev(values: list[float]) -> float:
    """Compute stdev, returning 0.0 for fewer than 2 values."""
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def _compute_holding_period(fills: list[dict]) -> dict:
    """Compute holding period statistics from fills.

    Since we don't have paired entry/exit data here, we categorize
    based on the fill metadata available.
    """
    # Placeholder: would need paired entry/exit fills for accurate calculation
    return {
        "median_minutes": 0,
        "category": "unknown",
    }


def _compute_entry_style(fills: list[dict], snapshots: list[dict]) -> dict:
    """Compute entry style profile per BASELINE.md section 2.4."""
    dist_vwaps = [s.get("dist_vwap_60", 0.0) for s in snapshots if "dist_vwap_60" in s]
    breakout_exts = [s.get("breakout_20", 0.0) for s in snapshots if "breakout_20" in s]

    # dist_ma20: (close - sma_20) / atr
    dist_ma20s = []
    for s in snapshots:
        sma_20 = s.get("sma_20")
        atr = s.get("atr_14")
        close = s.get("close") or s.get("vwap")  # approximate
        if sma_20 and atr and atr > 0 and close:
            dist_ma20s.append((close - sma_20) / atr)

    mean_dist_vwap = _safe_mean(dist_vwaps)
    mean_breakout_ext = _safe_mean(breakout_exts)
    mean_dist_ma20 = _safe_mean(dist_ma20s)

    # Classify entry style
    if mean_breakout_ext > 0.01:
        label = "breakout"
    elif mean_dist_vwap < -0.005:
        label = "pullback"
    else:
        label = "mean_reversion"

    return {
        "mean_dist_vwap": round(mean_dist_vwap, 4),
        "mean_breakout_extension": round(mean_breakout_ext, 4),
        "mean_dist_ma20": round(mean_dist_ma20, 4),
        "label": label,
    }


def _compute_risk_profile(
    fills: list[dict],
    snapshots: list[dict],
    account_balance: float,
) -> dict:
    """Compute risk profile per BASELINE.md section 3."""
    risk_pcts = []
    stop_atrs = []

    for fill, snapshot in zip(fills, snapshots):
        price = fill.get("price", 0)
        quantity = fill.get("quantity", 0)
        atr = snapshot.get("atr_14")

        # Extract stop from exit_intent if available
        exit_intent = fill.get("exit_intent") or {}
        stop_price = None
        if isinstance(exit_intent, dict):
            stop_price = exit_intent.get("stop_loss") or exit_intent.get("stop")

        if stop_price and price > 0:
            risk_per_share = abs(price - float(stop_price))
            total_risk = risk_per_share * quantity

            if account_balance > 0:
                risk_pcts.append((total_risk / account_balance) * 100)

            if atr and atr > 0:
                stop_atrs.append(risk_per_share / atr)

    return {
        "mean_risk_pct": round(_safe_mean(risk_pcts), 2),
        "mean_stop_atr": round(_safe_mean(stop_atrs), 2),
        "std_risk_pct": round(_safe_stdev(risk_pcts), 2),
    }


def _compute_entry_behavior(fills: list[dict], snapshots: list[dict]) -> dict:
    """Compute entry behavior metrics per BASELINE.md section 4."""
    vwap_extensions = []
    breakout_extensions = []
    ma20_distances = []
    inside_value_count = 0
    outside_value_count = 0
    wins_inside = 0
    wins_outside = 0
    losses_during_exhaustion = 0
    total_losses = 0

    for fill, snapshot in zip(fills, snapshots):
        # VWAP extension
        dist_vwap = snapshot.get("dist_vwap_60")
        if dist_vwap is not None:
            vwap_extensions.append(abs(dist_vwap))

        # Breakout extension
        breakout = snapshot.get("breakout_20")
        if breakout is not None:
            breakout_extensions.append(breakout)

        # MA20 distance
        sma_20 = snapshot.get("sma_20")
        atr = snapshot.get("atr_14")
        price = fill.get("price", 0)
        if sma_20 and atr and atr > 0 and price > 0:
            ma20_distances.append(abs((price - sma_20) / atr))

        # Value area classification
        vwap = snapshot.get("vwap")
        vwap_std = snapshot.get("stddev_20")
        if vwap and vwap_std and vwap_std > 0 and price > 0:
            if abs(price - vwap) <= vwap_std:
                inside_value_count += 1
            else:
                outside_value_count += 1

        # Losses during exhaustion
        rsi = snapshot.get("rsi_14")
        stoch_k = snapshot.get("stoch_k")
        is_exhaustion = (
            (rsi is not None and rsi > 75)
            or (stoch_k is not None and stoch_k > 85)
        )

        # Use side as proxy: buy fills that later become losses
        # Since we don't have PnL per fill, we track exhaustion entries
        if fill.get("side") == "buy" and is_exhaustion:
            losses_during_exhaustion += 1
        if fill.get("side") == "buy":
            total_losses += 1  # placeholder — actual loss tracking needs PnL

    total_fills = len(fills)
    pct_outside = outside_value_count / total_fills if total_fills > 0 else 0
    pct_losses_exhaustion = losses_during_exhaustion / total_losses if total_losses > 0 else 0

    return {
        "mean_vwap_extension": round(_safe_mean(vwap_extensions), 4),
        "mean_breakout_extension": round(_safe_mean(breakout_extensions), 4),
        "mean_ma20_distance": round(_safe_mean(ma20_distances), 4),
        "pct_outside_value": round(pct_outside, 4),
        "pct_losses_during_exhaustion": round(pct_losses_exhaustion, 4),
        "win_rate_inside_value": 0.0,  # Requires PnL data
        "win_rate_outside_value": 0.0,  # Requires PnL data
    }


def _compute_volatility_behavior(snapshots: list[dict]) -> dict:
    """Compute volatility behavior per BASELINE.md section 5."""
    decay_count = 0
    total = 0

    for snapshot in snapshots:
        rv_15 = snapshot.get("rv_15")
        rv_60 = snapshot.get("rv_60")
        if rv_15 is not None and rv_60 is not None and rv_60 > 0:
            total += 1
            if rv_15 < rv_60 * 0.6:
                decay_count += 1

    pct_decay = decay_count / total if total > 0 else 0

    return {
        "pct_volatility_decay_entries": round(pct_decay, 4),
        "preferred_regime": "unknown",  # Requires regime labels
    }


def _compute_psychological_metrics(snapshots: list[dict]) -> dict:
    """Compute FOMO index and discipline score per BASELINE.md section 6."""
    dist_vwaps = [s.get("dist_vwap_60", 0.0) for s in snapshots if "dist_vwap_60" in s]
    breakout_exts = [s.get("breakout_20", 0.0) for s in snapshots if "breakout_20" in s]

    # FOMO index: zscore(dist_vwap) + zscore(breakout_extension)
    # Simplified: use mean of absolute values, normalized to 0-100
    mean_vwap = _safe_mean([abs(v) for v in dist_vwaps])
    mean_breakout = _safe_mean([abs(v) for v in breakout_exts])

    # Scale: larger extensions → higher FOMO
    raw_fomo = (mean_vwap * 100 + mean_breakout * 100) / 2
    fomo_index = int(max(0, min(100, raw_fomo)))

    # Discipline score: 100 - variance penalties, normalized
    var_vwap = _safe_stdev(dist_vwaps) ** 2 if dist_vwaps else 0
    var_breakout = _safe_stdev(breakout_exts) ** 2 if breakout_exts else 0

    raw_discipline = 100 - (var_vwap * 200 + var_breakout * 200)
    discipline_score = int(max(0, min(100, raw_discipline)))

    return {
        "fomo_index": fomo_index,
        "discipline_score": discipline_score,
    }
