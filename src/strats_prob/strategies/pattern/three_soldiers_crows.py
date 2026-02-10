"""Strategy 88: Three White Soldiers / Three Black Crows (continuation).

Entry Long: cdl_3white_soldiers > 0.
Entry Short: cdl_3black_crows < 0.
Exit: trail 2*ATR or opposite pattern.
"""

from src.strats_prob.conditions import candle_bullish, candle_bearish
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=88,
    name="three_soldiers_crows",
    display_name="Three White Soldiers / Three Black Crows",
    philosophy="Three consecutive strong-bodied candles signal powerful trend "
               "continuation with conviction from buyers or sellers.",
    category="pattern",
    tags=["pattern", "trend", "long_short", "pattern", "trailing",
          "CDL3WHITESOLDIERS", "CDL3BLACKCROWS", "ATR", "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        candle_bullish("cdl_3white_soldiers"),
    ],
    entry_short=[
        candle_bearish("cdl_3black_crows"),
    ],
    exit_long=[
        candle_bearish("cdl_3black_crows"),
    ],
    exit_short=[
        candle_bullish("cdl_3white_soldiers"),
    ],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["cdl_3white_soldiers", "cdl_3black_crows", "atr_14"],
    details={
        "entry_long": "Three white soldiers pattern (cdl_3white_soldiers > 0)",
        "entry_short": "Three black crows pattern (cdl_3black_crows < 0)",
        "exit": "Trailing stop 2*ATR or opposite pattern",
        "indicators": ["CDL_3WHITE_SOLDIERS", "CDL_3BLACK_CROWS", "ATR(14)"],
        "tags": ["pattern", "trend", "long_short", "swing"],
    },
)
