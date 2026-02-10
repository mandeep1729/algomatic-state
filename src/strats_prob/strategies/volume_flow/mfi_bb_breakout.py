"""Strategy 74: MFI + BB Breakout.

Entry Long: close > BB upper AND MFI > 60.
Entry Short: close < BB lower AND MFI < 40.
Exit: target 3*ATR; stop 2*ATR; or BB middle cross.
"""

from src.strats_prob.conditions import above, below, crosses_below, crosses_above
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=74,
    name="mfi_bb_breakout",
    display_name="MFI + BB Breakout",
    philosophy="Bollinger Band breakouts with strong money flow confirm volume-backed momentum.",
    category="volume_flow",
    tags=["volume_flow", "breakout", "long_short", "breakout", "atr_stop",
          "atr_target", "MFI", "BBANDS", "ATR", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        above("close", "bb_upper"),
        above("mfi_14", 60),
    ],
    entry_short=[
        below("close", "bb_lower"),
        below("mfi_14", 40),
    ],
    exit_long=[
        crosses_below("close", "bb_middle"),
    ],
    exit_short=[
        crosses_above("close", "bb_middle"),
    ],
    atr_stop_mult=2.0,
    atr_target_mult=3.0,
    required_indicators=["bb_upper", "bb_lower", "bb_middle", "mfi_14", "atr_14"],
    details={
        "entry_long": "Close > BB upper AND MFI > 60",
        "entry_short": "Close < BB lower AND MFI < 40",
        "exit": "Target 3*ATR; stop 2*ATR; or BB middle cross",
        "indicators": ["BBANDS(20,2,2)", "MFI(14)", "ATR(14)"],
        "tags": ["volume_flow", "breakout", "long_short", "swing"],
    },
)
