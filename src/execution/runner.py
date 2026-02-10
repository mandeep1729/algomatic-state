"""Trading runner for orchestrating live and paper trading.

NOTE: This module requires reimplementation of the strategy module.
See: docs/archive/STATE_VECTOR_HMM_IMPLEMENTATION_PLAN.md
"""

import time
import signal
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Protocol

import numpy as np
import pandas as pd

from src.data.loaders.alpaca_loader import AlpacaLoader
from src.execution.client import AlpacaClient, AccountInfo
from src.execution.orders import Order, OrderStatus
from src.execution.order_manager import OrderManager, Signal
from src.execution.order_tracker import OrderTracker, OrderUpdate, PositionTracker
from src.execution.risk_manager import RiskManager, RiskConfig, RiskViolation
from src.features.pipeline import FeaturePipeline
from src.utils.logging import get_logger, TradeLogger


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


logger = get_logger(__name__)


@dataclass
class TradingRunnerConfig:
    """Configuration for the trading runner.

    Attributes:
        symbols: List of symbols to trade
        bar_interval_seconds: Seconds between bar fetches
        signal_interval_seconds: Seconds between signal generation
        warmup_bars: Number of historical bars for warmup
        max_positions: Maximum concurrent positions
        paper: Use paper trading
        risk_config: Risk management configuration
        log_dir: Directory for trade logs
        enable_order_tracking: Enable real-time order tracking
        dry_run: Generate signals but don't submit orders
    """

    symbols: list[str] = field(default_factory=list)
    bar_interval_seconds: int = 60
    signal_interval_seconds: int = 60
    warmup_bars: int = 100
    max_positions: int = 10
    paper: bool = True
    risk_config: RiskConfig = field(default_factory=RiskConfig)
    log_dir: Path = field(default_factory=lambda: Path("logs/trading"))
    enable_order_tracking: bool = True
    dry_run: bool = False


class TradingRunner:
    """Orchestrates live/paper trading execution.

    Combines all execution components:
    - Data fetching
    - Feature computation
    - Signal generation
    - Risk checking
    - Order submission
    - Order tracking
    - Position management

    Example:
        config = TradingRunnerConfig(
            symbols=["AAPL", "MSFT"],
            paper=True,
        )
        runner = TradingRunner(config, strategy)

        # Run trading loop
        runner.run()  # Blocks until stopped

        # Or run with callbacks
        runner.on_signal(handle_signal)
        runner.on_fill(handle_fill)
        runner.run()
    """

    def __init__(
        self,
        config: TradingRunnerConfig,
        strategy: BaseStrategy,
        client: AlpacaClient | None = None,
    ):
        """Initialize the trading runner.

        Args:
            config: Runner configuration
            strategy: Trading strategy instance
            client: Alpaca client (created if None)
        """
        self._config = config
        self._strategy = strategy

        # Initialize client
        self._client = client or AlpacaClient(paper=config.paper)

        # Initialize components
        self._data_loader = AlpacaLoader(use_cache=False)
        self._feature_pipeline = FeaturePipeline()
        self._order_manager = OrderManager(self._client)
        self._risk_manager = RiskManager(self._client, config.risk_config)
        self._order_tracker = OrderTracker(self._client)
        self._position_tracker = PositionTracker(self._client)

        # Setup trade logging
        config.log_dir.mkdir(parents=True, exist_ok=True)
        self._trade_logger = TradeLogger(str(config.log_dir / "trades.jsonl"))

        # State
        self._running = False
        self._shutdown_requested = False
        self._last_bar_time: dict[str, datetime] = {}
        self._data_cache: dict[str, pd.DataFrame] = {}
        self._features_cache: dict[str, pd.DataFrame] = {}

        # Callbacks
        self._signal_callbacks: list[Callable[[Signal], None]] = []
        self._fill_callbacks: list[Callable[[OrderUpdate], None]] = []
        self._error_callbacks: list[Callable[[Exception], None]] = []

        # Setup signal handlers
        self._setup_signal_handlers()

    @property
    def is_running(self) -> bool:
        """Check if runner is active."""
        return self._running

    @property
    def client(self) -> AlpacaClient:
        """Get the Alpaca client."""
        return self._client

    @property
    def order_manager(self) -> OrderManager:
        """Get the order manager."""
        return self._order_manager

    @property
    def risk_manager(self) -> RiskManager:
        """Get the risk manager."""
        return self._risk_manager

    def on_signal(self, callback: Callable[[Signal], None]) -> None:
        """Register a callback for signal events."""
        self._signal_callbacks.append(callback)

    def on_fill(self, callback: Callable[[OrderUpdate], None]) -> None:
        """Register a callback for fill events."""
        self._fill_callbacks.append(callback)

    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """Register a callback for error events."""
        self._error_callbacks.append(callback)

    def _setup_signal_handlers(self) -> None:
        """Setup OS signal handlers for graceful shutdown."""
        def handle_shutdown(signum: int, frame: Any) -> None:
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self._shutdown_requested = True

        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)

    def initialize(self) -> None:
        """Initialize the runner (fetch initial data, sync positions)."""
        logger.info("Initializing trading runner...")

        # Initialize risk manager
        self._risk_manager.initialize()

        # Sync positions
        self._position_tracker.sync()

        # Setup order tracker callbacks
        self._order_tracker.on_fill(self._handle_fill)

        # Fetch warmup data
        self._fetch_warmup_data()

        logger.info(
            f"Runner initialized",
            extra={
                "symbols": self._config.symbols,
                "positions": len(self._position_tracker.positions),
            },
        )

    def _fetch_warmup_data(self) -> None:
        """Fetch historical data for warmup."""
        logger.info("Fetching warmup data...")

        end = datetime.now()
        # Estimate start time (assuming 1-min bars, 390 bars/day)
        days_needed = max(1, self._config.warmup_bars // 390 + 1)
        start = end - timedelta(days=days_needed * 2)  # Extra buffer for weekends

        for symbol in self._config.symbols:
            try:
                df = self._data_loader.load(
                    source=symbol,
                    start=start,
                    end=end,
                )

                if not df.empty:
                    # Keep only required warmup bars
                    df = df.tail(self._config.warmup_bars)
                    self._data_cache[symbol] = df

                    # Compute features
                    features = self._feature_pipeline.compute(df)
                    self._features_cache[symbol] = features.dropna()

                    self._last_bar_time[symbol] = df.index[-1]

                    logger.info(
                        f"Loaded warmup data for {symbol}",
                        extra={
                            "bars": len(df),
                            "features": len(self._features_cache[symbol]),
                        },
                    )

            except Exception as e:
                logger.error(f"Failed to load warmup data for {symbol}", extra={"error": str(e)})

    def run(self) -> None:
        """Run the main trading loop.

        Blocks until shutdown is requested or error occurs.
        """
        self._running = True
        logger.info("Starting trading loop...")

        # Start order tracker if enabled
        if self._config.enable_order_tracking:
            self._order_tracker.start()

        try:
            while self._running and not self._shutdown_requested:
                try:
                    # Check if market is open
                    if not self._client.is_market_open():
                        logger.debug("Market closed, waiting...")
                        time.sleep(60)
                        continue

                    # Check if trading is allowed
                    allowed, reason = self._risk_manager.is_trading_allowed()
                    if not allowed:
                        logger.warning(f"Trading not allowed: {reason}")
                        time.sleep(60)
                        continue

                    # Run trading cycle
                    self._trading_cycle()

                    # Wait for next cycle
                    time.sleep(self._config.signal_interval_seconds)

                except Exception as e:
                    logger.error(f"Error in trading loop", extra={"error": str(e)})
                    self._notify_error(e)
                    time.sleep(10)  # Brief pause before retrying

        finally:
            self._running = False
            self._shutdown()

    def _trading_cycle(self) -> None:
        """Execute one trading cycle."""
        logger.debug("Starting trading cycle for %d symbols", len(self._config.symbols))
        # Fetch latest bars
        self._fetch_latest_bars()

        # Sync order status
        self._order_manager.sync_orders()

        # Get account and positions
        account = self._client.get_account()
        positions = self._client.get_positions()

        # Generate and process signals for each symbol
        for symbol in self._config.symbols:
            try:
                signal = self._generate_signal(symbol)

                if signal is None or signal.is_exit and self._position_tracker.get_position(symbol) == 0:
                    continue

                # Notify callbacks
                self._notify_signal(signal)

                # Process signal
                if not self._config.dry_run:
                    self._process_signal(signal, account, positions)

            except Exception as e:
                logger.error(f"Error processing {symbol}", extra={"error": str(e)})

    def _fetch_latest_bars(self) -> None:
        """Fetch latest bar data for all symbols."""
        for symbol in self._config.symbols:
            try:
                last_time = self._last_bar_time.get(symbol)
                if last_time is None:
                    continue

                # Fetch new bars since last known time
                start = last_time + timedelta(minutes=1)
                end = datetime.now()

                if end <= start:
                    continue

                df = self._data_loader.load(
                    source=symbol,
                    start=start,
                    end=end,
                )

                if df.empty:
                    continue

                # Append to cache
                if symbol in self._data_cache:
                    self._data_cache[symbol] = pd.concat([
                        self._data_cache[symbol],
                        df,
                    ]).tail(self._config.warmup_bars)
                else:
                    self._data_cache[symbol] = df

                # Recompute features
                features = self._feature_pipeline.compute(self._data_cache[symbol])
                self._features_cache[symbol] = features.dropna()

                self._last_bar_time[symbol] = self._data_cache[symbol].index[-1]

            except Exception as e:
                logger.error(f"Failed to fetch bars for {symbol}", extra={"error": str(e)})

    def _generate_signal(self, symbol: str) -> Signal | None:
        """Generate trading signal for a symbol.

        Args:
            symbol: Asset symbol

        Returns:
            Signal or None if no signal
        """
        logger.debug("Generating signal for %s", symbol)
        features = self._features_cache.get(symbol)
        if features is None or features.empty:
            logger.debug("No features available for %s", symbol)
            return None

        # Use the latest feature row
        latest_features = features.iloc[-1:]

        # Generate signal from strategy
        signals = self._strategy.generate_signals(latest_features)

        # Find signal for this symbol
        for signal in signals:
            if signal.symbol == symbol:
                logger.debug(
                    "Signal generated for %s: direction=%s, strength=%.2f",
                    symbol, signal.direction.value, signal.strength,
                )
                return signal

        logger.debug("No signal generated for %s", symbol)
        return None

    def _process_signal(
        self,
        signal: Signal,
        account: AccountInfo,
        positions: list,
    ) -> None:
        """Process a trading signal.

        Args:
            signal: Trading signal
            account: Current account info
            positions: Current positions
        """
        logger.debug(
            "Processing signal: symbol=%s, is_exit=%s, account_equity=%.2f",
            signal.symbol, signal.is_exit, account.equity,
        )
        if signal.is_exit:
            # Close position
            self._handle_exit_signal(signal)
        else:
            # Entry signal
            self._handle_entry_signal(signal, account, positions)

    def _handle_entry_signal(
        self,
        signal: Signal,
        account: AccountInfo,
        positions: list,
    ) -> None:
        """Handle an entry signal.

        Args:
            signal: Entry signal
            account: Current account info
            positions: Current positions
        """
        # Get current price (use last close from cache)
        data = self._data_cache.get(signal.symbol)
        if data is None or data.empty:
            return

        current_price = data["close"].iloc[-1]

        # Convert signal to order
        order = self._order_manager.signal_to_order(signal, current_price)
        if order is None:
            return

        # Check risk limits
        violations = self._risk_manager.check_order(
            order,
            price=current_price,
            account=account,
            positions=positions,
        )

        if violations:
            for v in violations:
                logger.warning(
                    f"Order blocked by risk manager",
                    extra={
                        "symbol": signal.symbol,
                        "violation": str(v),
                    },
                )
            return

        # Submit order
        try:
            submitted = self._order_manager.submit_order(order)

            # Track order
            if self._config.enable_order_tracking:
                self._order_tracker.track_order(submitted)

            # Log trade
            self._trade_logger.log_trade(
                timestamp=datetime.now(),
                symbol=signal.symbol,
                side=str(order.side),
                quantity=order.quantity,
                price=current_price,
                metadata={
                    "signal_strength": signal.strength,
                    "regime_label": signal.metadata.regime_label,
                    "order_id": submitted.broker_order_id,
                },
            )

            logger.info(
                f"Submitted entry order",
                extra={
                    "symbol": signal.symbol,
                    "side": str(order.side),
                    "quantity": order.quantity,
                    "order_id": submitted.broker_order_id,
                },
            )

        except Exception as e:
            logger.error(f"Failed to submit order", extra={"error": str(e)})

    def _handle_exit_signal(self, signal: Signal) -> None:
        """Handle an exit signal.

        Args:
            signal: Exit signal
        """
        position_qty = self._position_tracker.get_position(signal.symbol)

        if position_qty == 0:
            return

        try:
            # Close position
            order = self._client.close_position(signal.symbol)

            if order:
                # Track order
                if self._config.enable_order_tracking:
                    self._order_tracker.track_order(order)

                logger.info(
                    f"Submitted exit order",
                    extra={
                        "symbol": signal.symbol,
                        "quantity": position_qty,
                        "order_id": order.broker_order_id,
                    },
                )

        except Exception as e:
            logger.error(f"Failed to close position", extra={"error": str(e)})

    def _handle_fill(self, update: OrderUpdate) -> None:
        """Handle a fill event.

        Args:
            update: Order update with fill information
        """
        # Update position tracker
        self._position_tracker.update_from_fill(update)

        # Log fill
        self._trade_logger.log_trade(
            timestamp=datetime.now(),
            symbol=update.order.symbol,
            side=str(update.order.side),
            quantity=update.fill_quantity,
            price=update.fill_price,
            metadata={
                "order_id": update.order.broker_order_id,
                "fill_type": "partial" if update.order.status == OrderStatus.PARTIALLY_FILLED else "complete",
            },
        )

        # Notify callbacks
        for callback in self._fill_callbacks:
            try:
                callback(update)
            except Exception as e:
                logger.error(f"Fill callback error", extra={"error": str(e)})

    def _notify_signal(self, signal: Signal) -> None:
        """Notify signal callbacks.

        Args:
            signal: Generated signal
        """
        for callback in self._signal_callbacks:
            try:
                callback(signal)
            except Exception as e:
                logger.error(f"Signal callback error", extra={"error": str(e)})

    def _notify_error(self, error: Exception) -> None:
        """Notify error callbacks.

        Args:
            error: Exception that occurred
        """
        for callback in self._error_callbacks:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error callback error", extra={"error": str(e)})

    def _shutdown(self) -> None:
        """Perform graceful shutdown."""
        logger.info("Shutting down trading runner...")

        # Stop order tracker
        self._order_tracker.stop()

        # Cancel pending orders
        try:
            cancelled = self._order_manager.cancel_all_orders()
            logger.info(f"Cancelled {cancelled} pending orders")
        except Exception as e:
            logger.error(f"Failed to cancel orders", extra={"error": str(e)})

        logger.info("Trading runner shutdown complete")

    def stop(self) -> None:
        """Request graceful shutdown."""
        self._shutdown_requested = True

    def emergency_stop(self) -> None:
        """Emergency stop - close all positions and cancel all orders."""
        logger.warning("EMERGENCY STOP initiated")

        try:
            # Cancel all orders
            self._order_manager.cancel_all_orders()

            # Close all positions
            self._order_manager.close_all_positions()

            logger.warning("Emergency stop complete - all positions closed")

        except Exception as e:
            logger.error(f"Emergency stop error", extra={"error": str(e)})

        self.stop()

    def get_status(self) -> dict[str, Any]:
        """Get current runner status.

        Returns:
            Dictionary with status information
        """
        account = self._client.get_account()
        positions = self._client.get_positions()

        return {
            "running": self._running,
            "market_open": self._client.is_market_open(),
            "paper": self._config.paper,
            "symbols": self._config.symbols,
            "account": {
                "equity": account.equity,
                "buying_power": account.buying_power,
                "portfolio_value": account.portfolio_value,
            },
            "positions": {p.symbol: p.quantity for p in positions},
            "pending_orders": len(self._order_manager.pending_orders),
            "risk": self._risk_manager.get_risk_summary(account, positions),
        }
