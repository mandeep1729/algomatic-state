"""Strategy 38: Donchian Middle Reversion.

Entry Long: close < donchian_low_20 then close back above.
Entry Short: close > donchian_high_20 then close back below.
Exit: donchian_mid_20 touch OR time 20 OR stop 2*ATR.
"""

from src.strats_prob.conditions import crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=38,
    name="donchian_middle_reversion",
    display_name="Donchian Middle Reversion",
    philosophy="Price breaking Donchian extremes and recovering signals exhaustion; reversion to midpoint follows.",
    category="mean_reversion",
    tags=["mean_reversion", "long_short", "pullback", "time",
          "MAX", "MIN", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        crosses_above("close", "donchian_low_20"),
    ],
    entry_short=[
        crosses_below("close", "donchian_high_20"),
    ],
    exit_long=[
        crosses_above("close", "donchian_mid_20"),
    ],
    exit_short=[
        crosses_below("close", "donchian_mid_20"),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=20,
    required_indicators=["close", "donchian_high_20", "donchian_low_20", "donchian_mid_20", "atr_14"],
    details={
        "entry_long": "Close was below donchian_low_20 and crosses back above",
        "entry_short": "Close was above donchian_high_20 and crosses back below",
        "exit": "donchian_mid_20 touch OR time stop 20 OR stop 2*ATR",
        "indicators": ["Donchian(20)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "pullback", "swing"],
    },
)
