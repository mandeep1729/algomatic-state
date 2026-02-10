"""Strategy 54: BB Squeeze Breakout (classic).

Setup: BB width lowest of last 60 bars.
Entry: first close outside upper (long) / below lower (short).
Exit: trail 2*ATR or opposite close back inside bands for 2 bars.
"""

from src.strats_prob.conditions import above, below, squeeze
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=54,
    name="bb_squeeze_breakout",
    display_name="BB Squeeze Breakout",
    philosophy="Volatility contraction (squeeze) precedes expansion; trade the first break.",
    category="breakout",
    tags=["breakout", "volatility", "long_short", "breakout", "atr_stop",
          "BBANDS", "ATR", "vol_contract", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        squeeze("bb_width", 60),
        above("close", "bb_upper"),
    ],
    entry_short=[
        squeeze("bb_width", 60),
        below("close", "bb_lower"),
    ],
    exit_long=[
        below("close", "bb_upper"),
    ],
    exit_short=[
        above("close", "bb_lower"),
    ],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["bb_upper", "bb_lower", "bb_width", "atr_14"],
    details={
        "entry_long": "BB width at 60-bar low AND close > BB upper",
        "entry_short": "BB width at 60-bar low AND close < BB lower",
        "exit": "Trail 2*ATR or close back inside bands",
        "indicators": ["BBANDS(20,2,2)", "ATR(14)"],
        "tags": ["breakout", "volatility", "long_short", "swing"],
    },
)
