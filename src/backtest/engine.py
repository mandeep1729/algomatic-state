"""Event-driven backtesting engine.

NOTE: This module requires reimplementation of the strategy module.
The strategy classes (BaseStrategy, Signal, SignalDirection) have been
removed as part of the HMM regime tracking system redesign.

See: docs/STATE_VECTOR_HMM_IMPLEMENTATION_PLAN.md
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

import numpy as np
import pandas as pd

from src.backtest.metrics import PerformanceMetrics, calculate_metrics

logger = logging.getLogger(__name__)


# Placeholder types until strategy module is reimplemented
class SignalDirection(Enum):
    """Trading signal direction."""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class Signal:
    """Placeholder signal class."""
    timestamp: datetime
    symbol: str
    direction: SignalDirection
    strength: float = 1.0
    size: float = 0.0
    metadata: dict = field(default_factory=dict)

    @property
    def is_long(self) -> bool:
        return self.direction == SignalDirection.LONG

    @property
    def is_short(self) -> bool:
        return self.direction == SignalDirection.SHORT


class BaseStrategy(Protocol):
    """Protocol for strategy implementations."""

    def generate_signals(
        self,
        features: pd.DataFrame,
        timestamp: datetime | None = None,
        state: np.ndarray | None = None,
    ) -> list[Signal]:
        """Generate trading signals from features."""
        ...


@dataclass
class BacktestConfig:
    """Configuration for backtesting.

    Attributes:
        initial_capital: Starting portfolio value
        commission_per_share: Commission per share traded
        slippage_bps: Slippage in basis points
        fill_on_next_bar: Whether to fill orders on next bar open
        allow_fractional_shares: Whether to allow fractional share positions
        max_position_pct: Maximum position as fraction of portfolio
        risk_free_rate: Annual risk-free rate for metrics
    """

    initial_capital: float = 100000.0
    commission_per_share: float = 0.005
    slippage_bps: float = 5.0
    fill_on_next_bar: bool = True
    allow_fractional_shares: bool = True
    max_position_pct: float = 1.0
    risk_free_rate: float = 0.0


@dataclass
class Position:
    """Represents a position in an asset.

    Attributes:
        symbol: Asset symbol
        quantity: Number of shares (negative for short)
        avg_price: Average entry price
        entry_time: When position was opened
        unrealized_pnl: Current unrealized P&L
    """

    symbol: str
    quantity: float
    avg_price: float
    entry_time: datetime
    unrealized_pnl: float = 0.0

    @property
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.quantity < 0

    @property
    def market_value(self) -> float:
        """Current market value at entry price."""
        return abs(self.quantity * self.avg_price)

    def update_pnl(self, current_price: float) -> None:
        """Update unrealized P&L.

        Args:
            current_price: Current market price
        """
        if self.quantity > 0:
            self.unrealized_pnl = self.quantity * (current_price - self.avg_price)
        else:
            self.unrealized_pnl = abs(self.quantity) * (self.avg_price - current_price)


@dataclass
class Trade:
    """Represents a completed trade.

    Attributes:
        symbol: Asset symbol
        direction: Trade direction
        quantity: Number of shares
        entry_price: Entry price
        exit_price: Exit price
        entry_time: Entry timestamp
        exit_time: Exit timestamp
        pnl: Realized profit/loss
        commission: Commission paid
        slippage: Slippage cost
    """

    symbol: str
    direction: SignalDirection
    quantity: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    commission: float = 0.0
    slippage: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert trade to dictionary."""
        return {
            "symbol": self.symbol,
            "direction": self.direction.value,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "pnl": self.pnl,
            "commission": self.commission,
            "slippage": self.slippage,
        }


@dataclass
class BacktestResult:
    """Results from a backtest run.

    Attributes:
        equity_curve: Series of portfolio values
        positions_history: History of positions at each timestamp
        trades: List of completed trades
        signals: List of all signals generated
        metrics: Performance metrics
        config: Configuration used
    """

    equity_curve: pd.Series
    positions_history: list[dict[str, Any]]
    trades: list[Trade]
    signals: list[Signal]
    metrics: PerformanceMetrics
    config: BacktestConfig

    def to_dict(self) -> dict[str, Any]:
        """Convert results to dictionary."""
        return {
            "equity_curve": self.equity_curve.to_dict(),
            "trades": [t.to_dict() for t in self.trades],
            "metrics": self.metrics.to_dict(),
        }


class BacktestEngine:
    """Event-driven backtesting engine.

    Processes data bar-by-bar, generating signals and simulating
    execution with realistic costs.

    Example:
        >>> engine = BacktestEngine(config)
        >>> result = engine.run(data, strategy)
        >>> print(f"Sharpe: {result.metrics.sharpe_ratio:.2f}")
    """

    def __init__(self, config: BacktestConfig | None = None):
        """Initialize backtest engine.

        Args:
            config: Backtest configuration
        """
        self._config = config or BacktestConfig()
        self._reset_state()

    def _reset_state(self) -> None:
        """Reset internal state."""
        logger.debug("Resetting backtest state, initial_capital=%.2f", self._config.initial_capital)
        self._cash = self._config.initial_capital
        self._positions: dict[str, Position] = {}
        self._pending_orders: list[dict[str, Any]] = []
        self._trades: list[Trade] = []
        self._signals: list[Signal] = []
        self._equity_history: list[tuple[datetime, float]] = []
        self._positions_history: list[dict[str, Any]] = []

    @property
    def config(self) -> BacktestConfig:
        """Return configuration."""
        return self._config

    @property
    def cash(self) -> float:
        """Return current cash balance."""
        return self._cash

    @property
    def positions(self) -> dict[str, Position]:
        """Return current positions."""
        return self._positions

    def run(
        self,
        data: dict[str, pd.DataFrame],
        strategy: BaseStrategy,
        features: dict[str, pd.DataFrame] | None = None,
        states: dict[str, np.ndarray] | None = None,
    ) -> BacktestResult:
        """Run backtest on historical data.

        Args:
            data: Dictionary of OHLCV DataFrames by symbol
            strategy: Strategy to backtest
            features: Optional pre-computed features by symbol
            states: Optional pre-computed state vectors by symbol

        Returns:
            BacktestResult with performance data
        """
        self._reset_state()

        # Get all unique timestamps across all symbols
        all_timestamps = set()
        for df in data.values():
            all_timestamps.update(df.index.tolist())
        all_timestamps = sorted(all_timestamps)

        logger.info(
            "Starting backtest: %d symbols, %d timestamps",
            len(data), len(all_timestamps),
        )

        # Main event loop
        for i, timestamp in enumerate(all_timestamps):
            # 1. Get current bar data for all symbols
            current_bars = {}
            for symbol, df in data.items():
                if timestamp in df.index:
                    current_bars[symbol] = df.loc[timestamp]

            if not current_bars:
                continue

            # 2. Execute pending orders from previous bar
            if self._config.fill_on_next_bar and i > 0:
                self._execute_pending_orders(current_bars, timestamp)

            # 3. Update position P&L
            self._update_positions(current_bars)

            # 4. Record equity
            equity = self._calculate_equity(current_bars)
            self._equity_history.append((timestamp, equity))
            self._positions_history.append({
                "timestamp": timestamp,
                "cash": self._cash,
                "equity": equity,
                "positions": {s: {"qty": p.quantity, "avg_price": p.avg_price}
                              for s, p in self._positions.items()},
            })

            # 5. Generate signals
            for symbol, bar in current_bars.items():
                # Get features for this symbol/timestamp
                if features and symbol in features:
                    feature_df = features[symbol]
                    if timestamp in feature_df.index:
                        symbol_features = feature_df.loc[:timestamp]
                    else:
                        continue
                else:
                    # Use raw OHLCV as features
                    symbol_features = data[symbol].loc[:timestamp]

                # Get state if available
                state = None
                if states and symbol in states:
                    state_arr = states[symbol]
                    # Find corresponding state index
                    symbol_df = data[symbol]
                    if timestamp in symbol_df.index:
                        idx = symbol_df.index.get_loc(timestamp)
                        if idx < len(state_arr):
                            state = state_arr[idx]

                # Generate signals
                try:
                    signals = strategy.generate_signals(
                        symbol_features,
                        timestamp,
                        state=state,
                    )

                    for signal in signals:
                        # Override symbol if not set correctly
                        if signal.symbol == "default":
                            signal = Signal(
                                timestamp=signal.timestamp,
                                symbol=symbol,
                                direction=signal.direction,
                                strength=signal.strength,
                                size=signal.size,
                                metadata=signal.metadata,
                            )

                        self._signals.append(signal)
                        self._process_signal(signal, current_bars[symbol], timestamp)

                except Exception:
                    logger.exception(
                        "Error generating signals for %s at %s",
                        symbol, timestamp,
                    )

            # 6. Execute orders if not waiting for next bar
            if not self._config.fill_on_next_bar:
                self._execute_pending_orders(current_bars, timestamp)

        # Build equity curve
        equity_curve = pd.Series(
            dict(self._equity_history),
            name="equity",
        )

        # Calculate metrics
        metrics = calculate_metrics(
            equity_curve,
            [t.to_dict() for t in self._trades],
            risk_free_rate=self._config.risk_free_rate,
        )

        logger.info(
            "Backtest complete: %d trades, total_return=%.4f, sharpe=%.2f",
            metrics.total_trades, metrics.total_return, metrics.sharpe_ratio,
        )

        return BacktestResult(
            equity_curve=equity_curve,
            positions_history=self._positions_history,
            trades=self._trades,
            signals=self._signals,
            metrics=metrics,
            config=self._config,
        )

    def _process_signal(
        self,
        signal: Signal,
        bar: pd.Series,
        timestamp: datetime,
    ) -> None:
        """Process a trading signal.

        Args:
            signal: Trading signal
            bar: Current OHLCV bar
            timestamp: Current timestamp
        """
        symbol = signal.symbol
        current_position = self._positions.get(symbol)
        logger.debug(
            "Processing signal: symbol=%s, direction=%s, strength=%.2f, timestamp=%s",
            symbol, signal.direction.value, signal.strength, timestamp,
        )

        if signal.direction == SignalDirection.FLAT:
            # Exit signal - close position
            if current_position and current_position.quantity != 0:
                self._pending_orders.append({
                    "symbol": symbol,
                    "action": "close",
                    "timestamp": timestamp,
                })
        elif signal.direction == SignalDirection.LONG:
            # Long signal
            if current_position and current_position.is_short:
                # Close short first
                self._pending_orders.append({
                    "symbol": symbol,
                    "action": "close",
                    "timestamp": timestamp,
                })

            # Open long
            size = signal.size if signal.size > 0 else self._calculate_position_size(signal, bar)
            if size > 0:
                self._pending_orders.append({
                    "symbol": symbol,
                    "action": "buy",
                    "size": size,
                    "signal": signal,
                    "timestamp": timestamp,
                })

        elif signal.direction == SignalDirection.SHORT:
            # Short signal
            if current_position and current_position.is_long:
                # Close long first
                self._pending_orders.append({
                    "symbol": symbol,
                    "action": "close",
                    "timestamp": timestamp,
                })

            # Open short
            size = signal.size if signal.size > 0 else self._calculate_position_size(signal, bar)
            if size > 0:
                self._pending_orders.append({
                    "symbol": symbol,
                    "action": "sell",
                    "size": size,
                    "signal": signal,
                    "timestamp": timestamp,
                })

    def _calculate_position_size(self, signal: Signal, bar: pd.Series) -> float:
        """Calculate position size from signal.

        Args:
            signal: Trading signal
            bar: Current bar data

        Returns:
            Position size in dollars
        """
        # Use signal size if specified
        if signal.size > 0:
            return signal.size

        # Default to fraction of equity based on strength
        equity = self._calculate_equity({signal.symbol: bar})
        max_size = equity * self._config.max_position_pct
        return max_size * signal.strength

    def _execute_pending_orders(
        self,
        bars: dict[str, pd.Series],
        timestamp: datetime,
    ) -> None:
        """Execute pending orders.

        Args:
            bars: Current bar data by symbol
            timestamp: Current timestamp
        """
        orders_to_execute = self._pending_orders.copy()
        self._pending_orders = []
        if orders_to_execute:
            logger.debug("Executing %d pending orders at %s", len(orders_to_execute), timestamp)

        for order in orders_to_execute:
            symbol = order["symbol"]
            if symbol not in bars:
                continue

            bar = bars[symbol]
            fill_price = float(bar["open"])  # Fill at open

            # Apply slippage
            slippage_mult = 1 + (self._config.slippage_bps / 10000)
            if order["action"] == "buy":
                fill_price *= slippage_mult
            elif order["action"] == "sell":
                fill_price /= slippage_mult

            if order["action"] == "close":
                self._close_position(symbol, fill_price, timestamp)

            elif order["action"] == "buy":
                self._open_position(
                    symbol,
                    order["size"],
                    fill_price,
                    timestamp,
                    SignalDirection.LONG,
                )

            elif order["action"] == "sell":
                self._open_position(
                    symbol,
                    order["size"],
                    fill_price,
                    timestamp,
                    SignalDirection.SHORT,
                )

    def _open_position(
        self,
        symbol: str,
        size_dollars: float,
        fill_price: float,
        timestamp: datetime,
        direction: SignalDirection,
    ) -> None:
        """Open a new position.

        Args:
            symbol: Asset symbol
            size_dollars: Position size in dollars
            fill_price: Fill price
            timestamp: Timestamp
            direction: Position direction
        """
        logger.debug(
            "Opening position: symbol=%s, size=$%.2f, price=%.2f, direction=%s",
            symbol, size_dollars, fill_price, direction.value,
        )
        # Calculate shares
        shares = size_dollars / fill_price
        if not self._config.allow_fractional_shares:
            shares = int(shares)

        if shares == 0:
            return

        # Calculate costs
        commission = abs(shares) * self._config.commission_per_share
        slippage_cost = size_dollars * (self._config.slippage_bps / 10000)

        # Check if we have enough cash
        required_cash = size_dollars + commission
        if required_cash > self._cash:
            # Reduce size to fit available cash
            available_for_position = self._cash - commission
            if available_for_position <= 0:
                return
            shares = available_for_position / fill_price
            if not self._config.allow_fractional_shares:
                shares = int(shares)
            if shares == 0:
                return
            size_dollars = shares * fill_price
            commission = abs(shares) * self._config.commission_per_share

        # For short positions, shares are negative
        if direction == SignalDirection.SHORT:
            shares = -shares

        # Update cash
        self._cash -= size_dollars + commission

        # Create or update position
        if symbol in self._positions:
            # Average into existing position
            pos = self._positions[symbol]
            total_shares = pos.quantity + shares
            if total_shares != 0:
                pos.avg_price = (
                    pos.avg_price * abs(pos.quantity) + fill_price * abs(shares)
                ) / abs(total_shares)
                pos.quantity = total_shares
            else:
                del self._positions[symbol]
        else:
            self._positions[symbol] = Position(
                symbol=symbol,
                quantity=shares,
                avg_price=fill_price,
                entry_time=timestamp,
            )

    def _close_position(
        self,
        symbol: str,
        fill_price: float,
        timestamp: datetime,
    ) -> None:
        """Close an existing position.

        Args:
            symbol: Asset symbol
            fill_price: Fill price
            timestamp: Timestamp
        """
        if symbol not in self._positions:
            logger.debug("No position to close for %s", symbol)
            return

        pos = self._positions[symbol]
        logger.debug(
            "Closing position: symbol=%s, qty=%.2f, entry=%.2f, exit=%.2f",
            symbol, pos.quantity, pos.avg_price, fill_price,
        )

        # Calculate P&L
        if pos.is_long:
            pnl = pos.quantity * (fill_price - pos.avg_price)
        else:
            pnl = abs(pos.quantity) * (pos.avg_price - fill_price)

        # Calculate costs
        shares = abs(pos.quantity)
        commission = shares * self._config.commission_per_share
        slippage_cost = shares * fill_price * (self._config.slippage_bps / 10000)

        # Net P&L
        net_pnl = pnl - commission - slippage_cost

        # Update cash
        position_value = shares * fill_price
        self._cash += position_value + pnl - commission

        # Record trade
        self._trades.append(Trade(
            symbol=symbol,
            direction=SignalDirection.LONG if pos.is_long else SignalDirection.SHORT,
            quantity=shares,
            entry_price=pos.avg_price,
            exit_price=fill_price,
            entry_time=pos.entry_time,
            exit_time=timestamp,
            pnl=net_pnl,
            commission=commission,
            slippage=slippage_cost,
        ))
        logger.debug(
            "Trade recorded: symbol=%s, pnl=%.2f, commission=%.2f",
            symbol, net_pnl, commission,
        )

        # Remove position
        del self._positions[symbol]

    def _update_positions(self, bars: dict[str, pd.Series]) -> None:
        """Update position P&L with current prices.

        Args:
            bars: Current bar data by symbol
        """
        for symbol, pos in self._positions.items():
            if symbol in bars:
                current_price = float(bars[symbol]["close"])
                pos.update_pnl(current_price)

    def _calculate_equity(self, bars: dict[str, pd.Series]) -> float:
        """Calculate current portfolio equity.

        Args:
            bars: Current bar data by symbol

        Returns:
            Total portfolio value
        """
        equity = self._cash

        for symbol, pos in self._positions.items():
            if symbol in bars:
                current_price = float(bars[symbol]["close"])
                if pos.is_long:
                    equity += pos.quantity * current_price
                else:
                    # Short position: we owe the shares
                    equity += pos.quantity * current_price + 2 * pos.quantity * pos.avg_price

        return equity
