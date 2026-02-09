"""Strategy 66: Gap + Go (simple).

Entry Long: open gaps up > 1*ATR above prior close AND close>open.
Entry Short: gap down >1*ATR AND close<open.
Exit: time 10 OR trail 1.5*ATR.
"""

from src.strats_prob.conditions import above, below, gap_down, gap_up
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=66,
    name="gap_and_go",
    display_name="Gap + Go",
    philosophy="Gaps backed by directional close signal continuation momentum.",
    category="breakout",
    tags=["breakout", "long_short", "breakout", "time",
          "ATR", "vol_expand", "scalp"],
    direction="long_short",
    entry_long=[
        gap_up(1.0),
        above("close", "open"),
    ],
    entry_short=[
        gap_down(1.0),
        below("close", "open"),
    ],
    exit_long=[],
    exit_short=[],
    trailing_atr_mult=1.5,
    atr_stop_mult=1.5,
    time_stop_bars=10,
    required_indicators=["open", "close", "atr_14"],
    details={
        "entry_long": "Gap up > 1*ATR AND close > open",
        "entry_short": "Gap down > 1*ATR AND close < open",
        "exit": "Time 10 bars OR trail 1.5*ATR",
        "indicators": ["ATR(14)"],
        "tags": ["breakout", "long_short", "scalp"],
    },
)
