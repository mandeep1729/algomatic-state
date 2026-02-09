"""Strategy 65: Volatility Contraction Pattern (VCP) Proxy.

Setup: ATR decreasing (falling) for 5 bars.
Entry Long: break above donchian_high_20.
Exit: trail 2*ATR.
"""

from src.strats_prob.conditions import breaks_above_level, falling
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=65,
    name="vcp_proxy",
    display_name="Volatility Contraction Pattern Proxy",
    philosophy="Decreasing ATR signals tightening volatility before an explosive breakout.",
    category="breakout",
    tags=["breakout", "volatility", "long_only", "breakout", "atr_stop",
          "ATR", "MAX", "vol_contract", "vol_expand", "swing"],
    direction="long_only",
    entry_long=[
        falling("atr_14", 5),
        breaks_above_level("donchian_high_20"),
    ],
    entry_short=[],
    exit_long=[],
    exit_short=[],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["atr_14", "donchian_high_20"],
    details={
        "entry_long": "ATR falling 5 bars AND close breaks 20-bar Donchian high",
        "entry_short": "N/A (long only)",
        "exit": "Trail 2*ATR",
        "indicators": ["ATR(14)", "Donchian(20)"],
        "tags": ["breakout", "volatility", "long_only", "swing"],
    },
)
