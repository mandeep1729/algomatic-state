"""Exit management for the probe engine.

Handles ATR-based stops, targets, trailing stops, and time stops
with risk-profile scaling.
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RiskProfile:
    """Risk profile that scales exit parameters."""

    name: str
    stop_scale: float
    target_scale: float
    trail_scale: float
    time_scale: float


RISK_PROFILES: dict[str, RiskProfile] = {
    "low": RiskProfile(name="low", stop_scale=0.75, target_scale=0.75, trail_scale=0.75, time_scale=0.6),
    "medium": RiskProfile(name="medium", stop_scale=1.0, target_scale=1.0, trail_scale=1.0, time_scale=1.0),
    "high": RiskProfile(name="high", stop_scale=1.5, target_scale=1.5, trail_scale=1.5, time_scale=1.5),
}


class ExitManager:
    """Manages exit logic for a single trade.

    Initialized at entry with risk-profile-scaled parameters.
    Call check() each bar to determine if the trade should be closed.
    Tracks max favorable excursion (MFE) and max adverse excursion (MAE).
    """

    def __init__(
        self,
        entry_price: float,
        direction: str,
        atr_at_entry: float,
        atr_stop_mult: Optional[float],
        atr_target_mult: Optional[float],
        trailing_atr_mult: Optional[float],
        time_stop_bars: Optional[int],
        risk_profile: RiskProfile,
    ):
        self.entry_price = entry_price
        self.direction = direction  # "long" or "short"
        self.atr = atr_at_entry
        self.risk_profile = risk_profile

        # Scale multipliers by risk profile
        self.stop_dist = (atr_stop_mult * risk_profile.stop_scale * self.atr) if atr_stop_mult else None
        self.target_dist = (atr_target_mult * risk_profile.target_scale * self.atr) if atr_target_mult else None
        self.trail_dist = (trailing_atr_mult * risk_profile.trail_scale * self.atr) if trailing_atr_mult else None
        self.time_limit = int(time_stop_bars * risk_profile.time_scale) if time_stop_bars else None

        # Tracking
        self.bars_held = 0
        self.best_price = entry_price
        self.worst_price = entry_price
        self._trailing_stop: Optional[float] = None

        if self.trail_dist:
            if direction == "long":
                self._trailing_stop = entry_price - self.trail_dist
            else:
                self._trailing_stop = entry_price + self.trail_dist

    def check(self, high: float, low: float, close: float) -> Optional[str]:
        """Check if any exit condition is met for this bar.

        Args:
            high: Current bar high
            low: Current bar low
            close: Current bar close

        Returns:
            Exit reason string, or None if no exit triggered.
        """
        self.bars_held += 1

        # Update MFE/MAE tracking
        if self.direction == "long":
            self.best_price = max(self.best_price, high)
            self.worst_price = min(self.worst_price, low)
        else:
            self.best_price = min(self.best_price, low)
            self.worst_price = max(self.worst_price, high)

        # 1. Fixed stop loss
        if self.stop_dist is not None:
            if self.direction == "long":
                stop_level = self.entry_price - self.stop_dist
                if low <= stop_level:
                    return "stop_loss"
            else:
                stop_level = self.entry_price + self.stop_dist
                if high >= stop_level:
                    return "stop_loss"

        # 2. Fixed target
        if self.target_dist is not None:
            if self.direction == "long":
                target_level = self.entry_price + self.target_dist
                if high >= target_level:
                    return "target"
            else:
                target_level = self.entry_price - self.target_dist
                if low <= target_level:
                    return "target"

        # 3. Trailing stop
        if self.trail_dist is not None and self._trailing_stop is not None:
            if self.direction == "long":
                new_trail = high - self.trail_dist
                self._trailing_stop = max(self._trailing_stop, new_trail)
                if low <= self._trailing_stop:
                    return "trailing_stop"
            else:
                new_trail = low + self.trail_dist
                self._trailing_stop = min(self._trailing_stop, new_trail)
                if high >= self._trailing_stop:
                    return "trailing_stop"

        # 4. Time stop
        if self.time_limit is not None and self.bars_held >= self.time_limit:
            return "time_stop"

        return None

    @property
    def max_drawdown_pct(self) -> float:
        """Maximum adverse excursion as a percentage of entry price."""
        if self.direction == "long":
            return (self.entry_price - self.worst_price) / self.entry_price
        else:
            return (self.worst_price - self.entry_price) / self.entry_price

    @property
    def max_profit_pct(self) -> float:
        """Maximum favorable excursion as a percentage of entry price."""
        if self.direction == "long":
            return (self.best_price - self.entry_price) / self.entry_price
        else:
            return (self.entry_price - self.best_price) / self.entry_price
