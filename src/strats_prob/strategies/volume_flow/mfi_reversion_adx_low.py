"""Strategy 78: MFI Reversion with ADX Low.

Entry Long: ADX < 15 AND MFI crosses up through 20.
Entry Short: ADX < 15 AND MFI crosses down through 80.
Exit: MFI 50 OR time 20 OR stop 2*ATR.
"""

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=78,
    name="mfi_reversion_adx_low",
    display_name="MFI Reversion with ADX Low",
    philosophy="In trendless markets (low ADX), extreme MFI readings revert to the mean, "
               "offering low-risk mean reversion opportunities.",
    category="volume_flow",
    tags=["volume_flow", "mean_reversion", "regime", "long_short", "threshold",
          "time", "MFI", "ADX", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        below("adx_14", 15),
        crosses_above("mfi_14", 20),
    ],
    entry_short=[
        below("adx_14", 15),
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
    required_indicators=["adx_14", "mfi_14", "atr_14"],
    details={
        "entry_long": "ADX < 15 AND MFI crosses up through 20",
        "entry_short": "ADX < 15 AND MFI crosses down through 80",
        "exit": "MFI reaches 50 OR time stop 20 OR stop 2*ATR",
        "indicators": ["ADX(14)", "MFI(14)", "ATR(14)"],
        "tags": ["volume_flow", "mean_reversion", "regime", "long_short", "swing"],
    },
)
