"""Core data structures for strategy probe definitions and trade results."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

import pandas as pd

# A condition function receives a features DataFrame (rows up to current bar index)
# and the current bar index (integer position), returning True/False.
ConditionFn = Callable[[pd.DataFrame, int], bool]


@dataclass
class ProbeTradeResult:
    """Result of a single simulated trade from the probe engine."""

    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    direction: str  # "long" or "short"
    pnl_pct: float
    bars_held: int
    max_drawdown_pct: float
    max_profit_pct: float
    exit_reason: str


@dataclass
class StrategyDef:
    """Declarative definition of one probe strategy.

    Composed of condition functions for entry/exit plus metadata for
    cataloging and DB persistence.
    """

    id: int
    name: str
    display_name: str
    philosophy: str
    category: str  # trend, mean_reversion, breakout, volume_flow, pattern, regime
    tags: list[str]
    direction: str  # long_short, long_only, short_only

    # Entry conditions: all must be True to trigger entry
    entry_long: list[ConditionFn] = field(default_factory=list)
    entry_short: list[ConditionFn] = field(default_factory=list)

    # Exit conditions (signal-based): any being True triggers exit
    exit_long: list[ConditionFn] = field(default_factory=list)
    exit_short: list[ConditionFn] = field(default_factory=list)

    # ATR-based exit multipliers (None = not used)
    atr_stop_mult: Optional[float] = 2.0
    atr_target_mult: Optional[float] = None
    trailing_atr_mult: Optional[float] = None
    time_stop_bars: Optional[int] = None

    # List of required indicator column names in the features DataFrame
    required_indicators: list[str] = field(default_factory=list)

    # Structured details for DB persistence
    details: dict = field(default_factory=dict)

    def to_db_dict(self) -> dict:
        """Convert to dict for ProbeRepository.seed_strategies()."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "philosophy": self.philosophy,
            "strategy_type": self.category,
            "direction": self.direction,
            "details": self.details,
        }
