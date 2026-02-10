"""Strategy 99: Volatility Breakout with 'Failure Exit'.

Entry: BB squeeze breakout (BB width at squeeze + break above upper / below lower).
Failure Exit: if close returns inside bands, exit immediately (signal exit).
Otherwise Exit: trail 2*ATR.
"""

from src.strats_prob.conditions import above, below, squeeze
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=99,
    name="vol_breakout_failure_exit",
    display_name="Volatility Breakout with Failure Exit",
    philosophy="Adding a failure exit to the classic squeeze breakout cuts losses "
               "quickly when the breakout does not follow through, improving risk-adjusted returns.",
    category="regime",
    tags=["breakout", "volatility", "long_short", "breakout", "signal",
          "atr_stop", "BBANDS", "ATR", "vol_expand", "swing"],
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
        below("close", "bb_upper"),  # failure: price returns inside bands
    ],
    exit_short=[
        above("close", "bb_lower"),  # failure: price returns inside bands
    ],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["bb_upper", "bb_lower", "bb_width", "atr_14"],
    details={
        "entry_long": "BB width at 60-bar squeeze AND close > BB upper",
        "entry_short": "BB width at 60-bar squeeze AND close < BB lower",
        "exit": "Failure: close returns inside bands; otherwise trail 2*ATR",
        "indicators": ["BBANDS(20,2,2)", "ATR(14)"],
        "tags": ["breakout", "volatility", "long_short", "swing"],
    },
)
