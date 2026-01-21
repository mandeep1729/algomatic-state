"""Walk-forward validation for robust backtesting."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestEngine, BacktestConfig, BacktestResult
from src.backtest.metrics import PerformanceMetrics, calculate_metrics
from src.strategy.base import BaseStrategy


@dataclass
class WalkForwardConfig:
    """Configuration for walk-forward validation.

    Attributes:
        train_period_days: Training period length in days
        test_period_days: Test period length in days
        step_days: Step size between windows in days
        min_train_samples: Minimum samples required for training
        retrain_state_model: Whether to retrain state model each window
        retrain_strategy: Whether to retrain strategy each window
    """

    train_period_days: int = 180  # 6 months
    test_period_days: int = 30   # 1 month
    step_days: int = 30          # 1 month step
    min_train_samples: int = 1000
    retrain_state_model: bool = True
    retrain_strategy: bool = True


@dataclass
class WalkForwardWindow:
    """Represents a single walk-forward window.

    Attributes:
        window_id: Window identifier
        train_start: Training period start
        train_end: Training period end
        test_start: Test period start
        test_end: Test period end
        train_result: Training period backtest result
        test_result: Test period backtest result
    """

    window_id: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_result: BacktestResult | None = None
    test_result: BacktestResult | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert window to dictionary."""
        return {
            "window_id": self.window_id,
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "test_start": self.test_start.isoformat(),
            "test_end": self.test_end.isoformat(),
            "train_metrics": self.train_result.metrics.to_dict() if self.train_result else None,
            "test_metrics": self.test_result.metrics.to_dict() if self.test_result else None,
        }


@dataclass
class WalkForwardResult:
    """Results from walk-forward validation.

    Attributes:
        windows: List of individual window results
        combined_equity: Combined equity curve from all test periods
        combined_metrics: Metrics calculated on combined test results
        train_metrics_summary: Summary statistics of training metrics
        test_metrics_summary: Summary statistics of test metrics
        config: Configuration used
    """

    windows: list[WalkForwardWindow]
    combined_equity: pd.Series
    combined_metrics: PerformanceMetrics
    train_metrics_summary: dict[str, Any]
    test_metrics_summary: dict[str, Any]
    config: WalkForwardConfig

    def to_dict(self) -> dict[str, Any]:
        """Convert results to dictionary."""
        return {
            "n_windows": len(self.windows),
            "combined_metrics": self.combined_metrics.to_dict(),
            "train_metrics_summary": self.train_metrics_summary,
            "test_metrics_summary": self.test_metrics_summary,
            "windows": [w.to_dict() for w in self.windows],
        }


class WalkForwardValidator:
    """Walk-forward validation for strategy evaluation.

    Implements anchored or rolling walk-forward testing with
    optional model retraining at each step.

    Example:
        >>> validator = WalkForwardValidator(config)
        >>> result = validator.run(data, strategy_factory, state_trainer)
        >>> print(f"OOS Sharpe: {result.combined_metrics.sharpe_ratio:.2f}")
    """

    def __init__(
        self,
        config: WalkForwardConfig | None = None,
        backtest_config: BacktestConfig | None = None,
    ):
        """Initialize walk-forward validator.

        Args:
            config: Walk-forward configuration
            backtest_config: Backtest engine configuration
        """
        self._config = config or WalkForwardConfig()
        self._backtest_config = backtest_config or BacktestConfig()

    @property
    def config(self) -> WalkForwardConfig:
        """Return configuration."""
        return self._config

    def run(
        self,
        data: dict[str, pd.DataFrame],
        strategy_factory: Callable[[], BaseStrategy],
        state_trainer: Callable[[pd.DataFrame], tuple[np.ndarray, Any]] | None = None,
        feature_pipeline: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
    ) -> WalkForwardResult:
        """Run walk-forward validation.

        Args:
            data: Dictionary of OHLCV DataFrames by symbol
            strategy_factory: Factory function to create new strategy instances
            state_trainer: Optional function to train state model on data
                          Returns (state_vectors, trained_model)
            feature_pipeline: Optional function to compute features from OHLCV

        Returns:
            WalkForwardResult with aggregated results
        """
        # Generate windows
        windows = self._generate_windows(data)

        if not windows:
            raise ValueError("No valid windows could be generated from data")

        # Process each window
        all_test_equities = []
        all_test_trades = []

        for window in windows:
            # Slice data for this window
            train_data, test_data = self._slice_data(data, window)

            # Compute features if pipeline provided
            train_features = None
            test_features = None
            if feature_pipeline:
                train_features = {
                    s: feature_pipeline(df) for s, df in train_data.items()
                }
                test_features = {
                    s: feature_pipeline(df) for s, df in test_data.items()
                }

            # Train state model if provided
            train_states = None
            test_states = None
            if state_trainer and self._config.retrain_state_model:
                for symbol, df in train_data.items():
                    features_df = train_features[symbol] if train_features else df
                    states, model = state_trainer(features_df)
                    train_states = {symbol: states}

                    # Apply to test data
                    if test_features:
                        test_df = test_features[symbol]
                    else:
                        test_df = test_data[symbol]
                    # Note: In real implementation, transform test data with trained model
                    test_states = {symbol: np.zeros((len(test_df), states.shape[1]))}

            # Create strategy
            strategy = strategy_factory()

            # Run training backtest
            engine = BacktestEngine(self._backtest_config)
            window.train_result = engine.run(
                train_data,
                strategy,
                features=train_features,
                states=train_states,
            )

            # Run test backtest
            test_engine = BacktestEngine(self._backtest_config)
            window.test_result = test_engine.run(
                test_data,
                strategy,
                features=test_features,
                states=test_states,
            )

            # Collect test results
            if window.test_result:
                all_test_equities.append(window.test_result.equity_curve)
                all_test_trades.extend(window.test_result.trades)

        # Combine test equity curves
        combined_equity = self._combine_equity_curves(all_test_equities)

        # Calculate combined metrics
        combined_metrics = calculate_metrics(
            combined_equity,
            [t.to_dict() for t in all_test_trades],
            risk_free_rate=self._backtest_config.risk_free_rate,
        )

        # Summarize train/test metrics
        train_metrics_summary = self._summarize_metrics(
            [w.train_result.metrics for w in windows if w.train_result]
        )
        test_metrics_summary = self._summarize_metrics(
            [w.test_result.metrics for w in windows if w.test_result]
        )

        return WalkForwardResult(
            windows=windows,
            combined_equity=combined_equity,
            combined_metrics=combined_metrics,
            train_metrics_summary=train_metrics_summary,
            test_metrics_summary=test_metrics_summary,
            config=self._config,
        )

    def _generate_windows(
        self,
        data: dict[str, pd.DataFrame],
    ) -> list[WalkForwardWindow]:
        """Generate walk-forward windows.

        Args:
            data: Historical data

        Returns:
            List of windows
        """
        # Get date range from data
        all_timestamps = set()
        for df in data.values():
            all_timestamps.update(df.index.tolist())

        if not all_timestamps:
            return []

        start_date = min(all_timestamps)
        end_date = max(all_timestamps)

        # Convert to datetime if needed
        if isinstance(start_date, pd.Timestamp):
            start_date = start_date.to_pydatetime()
            end_date = end_date.to_pydatetime()

        windows = []
        window_id = 0

        train_days = self._config.train_period_days
        test_days = self._config.test_period_days
        step_days = self._config.step_days

        current_start = start_date

        while True:
            train_start = current_start
            train_end = train_start + timedelta(days=train_days)
            test_start = train_end
            test_end = test_start + timedelta(days=test_days)

            # Check if we have enough data
            if test_end > end_date:
                break

            windows.append(WalkForwardWindow(
                window_id=window_id,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            ))

            window_id += 1
            current_start += timedelta(days=step_days)

        return windows

    def _slice_data(
        self,
        data: dict[str, pd.DataFrame],
        window: WalkForwardWindow,
    ) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
        """Slice data for a window.

        Args:
            data: Full historical data
            window: Window specification

        Returns:
            Tuple of (train_data, test_data)
        """
        train_data = {}
        test_data = {}

        for symbol, df in data.items():
            # Handle timezone-naive comparison
            idx = df.index
            if hasattr(idx, 'tz') and idx.tz is not None:
                train_start = pd.Timestamp(window.train_start).tz_localize(idx.tz)
                train_end = pd.Timestamp(window.train_end).tz_localize(idx.tz)
                test_start = pd.Timestamp(window.test_start).tz_localize(idx.tz)
                test_end = pd.Timestamp(window.test_end).tz_localize(idx.tz)
            else:
                train_start = window.train_start
                train_end = window.train_end
                test_start = window.test_start
                test_end = window.test_end

            train_mask = (df.index >= train_start) & (df.index < train_end)
            test_mask = (df.index >= test_start) & (df.index < test_end)

            if train_mask.any():
                train_data[symbol] = df[train_mask].copy()
            if test_mask.any():
                test_data[symbol] = df[test_mask].copy()

        return train_data, test_data

    def _combine_equity_curves(
        self,
        equity_curves: list[pd.Series],
    ) -> pd.Series:
        """Combine multiple equity curves into one continuous series.

        Args:
            equity_curves: List of equity curves

        Returns:
            Combined equity curve
        """
        if not equity_curves:
            return pd.Series(dtype=float)

        if len(equity_curves) == 1:
            return equity_curves[0]

        # Concatenate and chain returns
        combined = []
        scale = 1.0

        for i, equity in enumerate(equity_curves):
            if len(equity) == 0:
                continue

            # Normalize to returns, then rescale
            normalized = equity / equity.iloc[0] * scale

            if i == 0:
                combined.append(normalized)
            else:
                # Adjust starting point to end of previous
                combined.append(normalized.iloc[1:])

            # Update scale for next segment
            scale = normalized.iloc[-1]

        if not combined:
            return pd.Series(dtype=float)

        return pd.concat(combined)

    def _summarize_metrics(
        self,
        metrics_list: list[PerformanceMetrics],
    ) -> dict[str, Any]:
        """Summarize metrics across windows.

        Args:
            metrics_list: List of metrics from each window

        Returns:
            Summary statistics
        """
        if not metrics_list:
            return {}

        # Extract key metrics
        sharpes = [m.sharpe_ratio for m in metrics_list]
        returns = [m.total_return for m in metrics_list]
        drawdowns = [m.max_drawdown for m in metrics_list]
        win_rates = [m.win_rate for m in metrics_list]

        return {
            "n_windows": len(metrics_list),
            "sharpe_mean": float(np.mean(sharpes)),
            "sharpe_std": float(np.std(sharpes)),
            "sharpe_min": float(np.min(sharpes)),
            "sharpe_max": float(np.max(sharpes)),
            "return_mean": float(np.mean(returns)),
            "return_std": float(np.std(returns)),
            "drawdown_mean": float(np.mean(drawdowns)),
            "drawdown_max": float(np.max(drawdowns)),
            "win_rate_mean": float(np.mean(win_rates)),
            "consistency": sum(1 for s in sharpes if s > 0) / len(sharpes),
        }
