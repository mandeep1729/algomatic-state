"""Strategy 14: Linear Regression Slope + Price Filter.

Entry Long: LINEARREG_SLOPE(20)>0 AND close>SMA50.
Entry Short: slope<0 AND close<SMA50.
Exit: slope sign flips OR time stop 40 OR stop 2*ATR.
"""

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=14,
    name="linear_reg_slope_filter",
    display_name="Linear Regression Slope + Price Filter",
    philosophy="Linear regression slope quantifies trend direction; combined with SMA filter.",
    category="trend",
    tags=["trend", "long_short", "threshold", "time", "atr_stop",
          "LINEARREG_SLOPE", "SMA", "ATR", "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        above("linearreg_slope_20", 0),
        above("close", "sma_50"),
    ],
    entry_short=[
        below("linearreg_slope_20", 0),
        below("close", "sma_50"),
    ],
    exit_long=[
        crosses_below("linearreg_slope_20", 0),
    ],
    exit_short=[
        crosses_above("linearreg_slope_20", 0),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=40,
    required_indicators=["linearreg_slope_20", "sma_50", "atr_14"],
    details={
        "entry_long": "LINEARREG_SLOPE(20) > 0 AND close > SMA50",
        "entry_short": "LINEARREG_SLOPE(20) < 0 AND close < SMA50",
        "exit": "Slope sign flips OR time stop 40 bars OR stop 2*ATR",
        "indicators": ["LINEARREG_SLOPE(20)", "SMA(50)", "ATR(14)"],
        "tags": ["trend", "long_short", "threshold", "swing"],
    },
)
