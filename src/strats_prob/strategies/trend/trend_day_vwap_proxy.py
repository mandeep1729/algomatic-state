"""Strategy 20: Trend Day Filter with VWAP Proxy (Typical Price SMA).

Proxy: typical_price_sma_20.
Entry Long: close>typical_price_sma_20 AND ADX>20 AND RSI>55.
Exit: close<typical_price_sma_20 OR time stop 10 bars OR stop 1.5*ATR.
"""

from src.strats_prob.conditions import above, below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=20,
    name="trend_day_vwap_proxy",
    display_name="Trend Day Filter with VWAP Proxy",
    philosophy="VWAP proxy with ADX and RSI filters identifies intraday trending conditions.",
    category="trend",
    tags=["trend", "long_only", "threshold", "time", "SMA", "ADX", "ATR",
          "trend_favor", "scalp"],
    direction="long_only",
    entry_long=[
        above("close", "typical_price_sma_20"),
        above("adx_14", 20),
        above("rsi_14", 55),
    ],
    entry_short=[],
    exit_long=[
        below("close", "typical_price_sma_20"),
    ],
    exit_short=[],
    atr_stop_mult=1.5,
    time_stop_bars=10,
    required_indicators=["typical_price_sma_20", "adx_14", "rsi_14", "atr_14"],
    details={
        "entry_long": "Close > VWAP proxy AND ADX > 20 AND RSI > 55",
        "entry_short": "N/A (long only)",
        "exit": "Close < VWAP proxy OR time stop 10 bars OR stop 1.5*ATR",
        "indicators": ["Typical Price SMA(20)", "ADX(14)", "RSI(14)", "ATR(14)"],
        "tags": ["trend", "long_only", "threshold", "scalp"],
    },
)
