"""Strategy 33: MFI Extreme Fade.

Entry Long: MFI crosses up through 20.
Entry Short: MFI crosses down through 80.
Exit: MFI reaches 50 OR time stop 20 OR stop 2*ATR.
"""

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=33,
    name="mfi_extreme_fade",
    display_name="MFI Extreme Fade",
    philosophy="Money Flow Index at extremes signals volume-weighted overbought/oversold conditions.",
    category="mean_reversion",
    tags=["mean_reversion", "volume_flow", "long_short", "threshold", "time",
          "MFI", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        crosses_above("mfi_14", 20),
    ],
    entry_short=[
        crosses_below("mfi_14", 80),
    ],
    exit_long=[
        above("mfi_14", 50),
    ],
    exit_short=[
        below("mfi_14", 50),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=20,
    required_indicators=["mfi_14", "atr_14"],
    details={
        "entry_long": "MFI crosses up through 20",
        "entry_short": "MFI crosses down through 80",
        "exit": "MFI reaches 50 OR time stop 20 OR stop 2*ATR",
        "indicators": ["MFI(14)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "threshold", "swing"],
    },
)
