"""Strategy 12: Momentum + Pullback to BB Middle.

Entry Long: ADX>20 AND close>BB middle AND pullback to BB middle.
Entry Short: ADX>20 AND close<BB middle AND pullback below BB middle.
Exit: close crosses BB middle opposite OR trail 2*ATR.
"""

from src.strats_prob.conditions import (
    above,
    below,
    pullback_below,
    pullback_to,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=12,
    name="momentum_pullback_bb_middle",
    display_name="Momentum + Pullback to BB Middle",
    philosophy="Bollinger middle band acts as dynamic support/resistance in trending markets.",
    category="trend",
    tags=["trend", "long_short", "pullback", "trailing", "BBANDS", "ADX", "ATR",
          "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        above("adx_14", 20),
        above("close", "bb_middle"),
        pullback_to("bb_middle"),
    ],
    entry_short=[
        above("adx_14", 20),
        below("close", "bb_middle"),
        pullback_below("bb_middle"),
    ],
    exit_long=[
        below("close", "bb_middle"),
    ],
    exit_short=[
        above("close", "bb_middle"),
    ],
    atr_stop_mult=2.0,
    trailing_atr_mult=2.0,
    required_indicators=["bb_middle", "adx_14", "atr_14"],
    details={
        "entry_long": "ADX > 20 AND close > BB middle AND pullback to BB middle",
        "entry_short": "ADX > 20 AND close < BB middle AND pullback below BB middle",
        "exit": "Close crosses BB middle opposite OR trail 2*ATR",
        "indicators": ["BBANDS(20,2,2)", "ADX(14)", "ATR(14)"],
        "tags": ["trend", "long_short", "pullback", "swing"],
    },
)
