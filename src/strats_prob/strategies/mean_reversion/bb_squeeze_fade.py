"""Strategy 37: BB Squeeze -> Fade First Expansion (contrarian).

Setup: BB width lowest of last 50 bars.
Entry: first close outside BB upper -> short (fade); outside BB lower -> long (fade).
Exit: BB middle OR time 10 OR stop 2*ATR.
"""

from src.strats_prob.conditions import (
    above,
    below,
    crosses_above,
    crosses_below,
    squeeze,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=37,
    name="bb_squeeze_fade",
    display_name="BB Squeeze Fade First Expansion",
    philosophy="After extreme compression, the first breakout often fails; fading it captures the snap back.",
    category="mean_reversion",
    tags=["mean_reversion", "volatility", "long_short", "threshold", "atr_stop",
          "BBANDS", "ATR", "vol_contract", "scalp"],
    direction="long_short",
    entry_long=[
        squeeze("bb_width", lookback=50),
        below("close", "bb_lower"),
    ],
    entry_short=[
        squeeze("bb_width", lookback=50),
        above("close", "bb_upper"),
    ],
    exit_long=[
        crosses_above("close", "bb_middle"),
    ],
    exit_short=[
        crosses_below("close", "bb_middle"),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=10,
    required_indicators=["close", "bb_upper", "bb_middle", "bb_lower", "bb_width", "atr_14"],
    details={
        "entry_long": "BB width at 50-bar low AND close < BB lower (fade the break)",
        "entry_short": "BB width at 50-bar low AND close > BB upper (fade the break)",
        "exit": "BB middle touch OR time stop 10 OR stop 2*ATR",
        "indicators": ["BBANDS(20,2,2)", "ATR(14)"],
        "tags": ["mean_reversion", "volatility", "long_short", "scalp"],
    },
)
