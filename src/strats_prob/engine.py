"""Lightweight bar-by-bar probe engine for strategy backtesting.

Produces normalized % P&L per trade for fair comparison across strategies
and asset prices. No equity curves, commissions, or dollar sizing.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.strats_prob.exits import ExitManager, RiskProfile
from src.strats_prob.strategy_def import ConditionFn, ProbeTradeResult, StrategyDef

logger = logging.getLogger(__name__)


class ProbeEngine:
    """Run a single strategy definition across a bar series.

    Args:
        strategy: The strategy definition to execute.
        risk_profile: Risk profile controlling stop/target/trail/time scaling.
    """

    def __init__(self, strategy: StrategyDef, risk_profile: RiskProfile):
        self.strategy = strategy
        self.risk_profile = risk_profile

    def run(self, df: pd.DataFrame) -> list[ProbeTradeResult]:
        """Execute the strategy bar-by-bar on the given data.

        The DataFrame must contain OHLCV columns (open, high, low, close, volume)
        plus all required indicator columns for the strategy.

        Uses fill-on-next-bar semantics: when a signal fires on bar i,
        entry_price = open of bar i+1.

        Open trades at end of data are discarded per requirements.

        Args:
            df: Combined OHLCV + features DataFrame with datetime index.

        Returns:
            List of completed trade results.
        """
        if df.empty:
            logger.warning("Empty DataFrame passed to ProbeEngine.run()")
            return []

        trades: list[ProbeTradeResult] = []
        n_bars = len(df)

        # State
        position: Optional[str] = None  # None, "long", or "short"
        exit_manager: Optional[ExitManager] = None
        entry_bar_idx: Optional[int] = None
        entry_price: Optional[float] = None
        pending_signal: Optional[str] = None  # "long" or "short" signal waiting for next bar

        for i in range(n_bars):
            high_i = float(df["high"].iloc[i])
            low_i = float(df["low"].iloc[i])
            close_i = float(df["close"].iloc[i])
            open_i = float(df["open"].iloc[i])

            # Handle pending entry from previous bar's signal
            if pending_signal is not None and position is None:
                atr_val = self._get_atr(df, i)
                if atr_val is not None and atr_val > 0:
                    position = pending_signal
                    entry_price = open_i
                    entry_bar_idx = i
                    exit_manager = ExitManager(
                        entry_price=entry_price,
                        direction=position,
                        atr_at_entry=atr_val,
                        atr_stop_mult=self.strategy.atr_stop_mult,
                        atr_target_mult=self.strategy.atr_target_mult,
                        trailing_atr_mult=self.strategy.trailing_atr_mult,
                        time_stop_bars=self.strategy.time_stop_bars,
                        risk_profile=self.risk_profile,
                    )
                    logger.debug(
                        "Entered %s at bar %d, price=%.4f, atr=%.4f",
                        position, i, entry_price, atr_val,
                    )
                pending_signal = None
                # Skip checking exits on entry bar
                continue

            # If in a position, check exits
            if position is not None and exit_manager is not None:
                exit_reason: Optional[str] = None

                # Check signal-based exits first
                signal_exits = self.strategy.exit_long if position == "long" else self.strategy.exit_short
                for cond in signal_exits:
                    try:
                        if cond(df, i):
                            exit_reason = "signal_exit"
                            break
                    except (KeyError, IndexError, ValueError):
                        continue

                # Check mechanical exits (stop/target/trail/time)
                if exit_reason is None:
                    exit_reason = exit_manager.check(high_i, low_i, close_i)

                if exit_reason is not None:
                    # Determine exit price
                    exit_price = self._get_exit_price(
                        exit_reason, position, entry_price, exit_manager,
                        open_i, high_i, low_i, close_i,
                    )
                    pnl_pct = self._calc_pnl_pct(entry_price, exit_price, position)

                    trades.append(ProbeTradeResult(
                        entry_time=df.index[entry_bar_idx],
                        exit_time=df.index[i],
                        entry_price=entry_price,
                        exit_price=exit_price,
                        direction=position,
                        pnl_pct=pnl_pct,
                        bars_held=exit_manager.bars_held,
                        max_drawdown_pct=exit_manager.max_drawdown_pct,
                        max_profit_pct=exit_manager.max_profit_pct,
                        exit_reason=exit_reason,
                    ))
                    logger.debug(
                        "Exited %s at bar %d, pnl=%.4f%%, reason=%s",
                        position, i, pnl_pct * 100, exit_reason,
                    )

                    # Reset state
                    position = None
                    exit_manager = None
                    entry_bar_idx = None
                    entry_price = None

            # If flat, check entry signals (signal fires here, entry on next bar)
            if position is None and i < n_bars - 1:
                # Check long entry
                if self.strategy.direction in ("long_short", "long_only"):
                    if self._check_conditions(self.strategy.entry_long, df, i):
                        pending_signal = "long"
                        continue

                # Check short entry
                if self.strategy.direction in ("long_short", "short_only"):
                    if self._check_conditions(self.strategy.entry_short, df, i):
                        pending_signal = "short"
                        continue

        # Open trades at end of data are discarded
        if position is not None:
            logger.debug("Discarding open %s trade at end of data", position)

        return trades

    @staticmethod
    def _check_conditions(conditions: list[ConditionFn], df: pd.DataFrame, idx: int) -> bool:
        """Check if all conditions in the list are met."""
        if not conditions:
            return False
        for cond in conditions:
            try:
                if not cond(df, idx):
                    return False
            except (KeyError, IndexError, ValueError):
                return False
        return True

    @staticmethod
    def _get_atr(df: pd.DataFrame, idx: int) -> Optional[float]:
        """Safely get ATR value at bar index."""
        try:
            val = float(df["atr_14"].iloc[idx])
            if np.isnan(val) or np.isinf(val) or val <= 0:
                return None
            return val
        except (KeyError, IndexError):
            return None

    @staticmethod
    def _calc_pnl_pct(entry_price: float, exit_price: float, direction: str) -> float:
        """Calculate normalized P&L percentage."""
        if direction == "long":
            return (exit_price - entry_price) / entry_price
        else:
            return (entry_price - exit_price) / entry_price

    @staticmethod
    def _get_exit_price(
        exit_reason: str,
        direction: str,
        entry_price: float,
        exit_manager: ExitManager,
        open_price: float,
        high: float,
        low: float,
        close: float,
    ) -> float:
        """Determine the exit price based on the exit reason.

        For stop/target hits, use the stop/target level (approximation).
        For signal/time exits, use the close price.
        """
        if exit_reason == "stop_loss" and exit_manager.stop_dist is not None:
            if direction == "long":
                return entry_price - exit_manager.stop_dist
            else:
                return entry_price + exit_manager.stop_dist

        if exit_reason == "target" and exit_manager.target_dist is not None:
            if direction == "long":
                return entry_price + exit_manager.target_dist
            else:
                return entry_price - exit_manager.target_dist

        if exit_reason == "trailing_stop" and exit_manager._trailing_stop is not None:
            return exit_manager._trailing_stop

        # Signal exit, time stop, or unknown: exit at close
        return close
