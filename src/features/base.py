"""Base classes and utilities for feature engineering."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Numerical stability constant
EPS = 1e-9


@dataclass
class FeatureSpec:
    """Specification for a computed feature.

    Attributes:
        name: Feature column name
        description: Human-readable description
        lookback: Minimum lookback period in bars
        group: Feature group (e.g., 'returns', 'volatility')
    """

    name: str
    description: str
    lookback: int
    group: str


class BaseFeatureCalculator(ABC):
    """Abstract base class for feature calculators.

    Each calculator is responsible for computing a group of related features.
    Subclasses must implement the compute() method and feature_specs property.
    """

    @property
    @abstractmethod
    def feature_specs(self) -> list[FeatureSpec]:
        """Return list of feature specifications this calculator produces."""
        pass

    @abstractmethod
    def compute(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """Compute features from OHLCV data.

        Args:
            df: DataFrame with datetime index and columns: open, high, low, close, volume
            **kwargs: Additional data (e.g., market_df for market context features)

        Returns:
            DataFrame with computed feature columns (same index as input)
        """
        pass

    @property
    def max_lookback(self) -> int:
        """Maximum lookback period required by this calculator."""
        return max(spec.lookback for spec in self.feature_specs) if self.feature_specs else 0


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Safely divide two series, avoiding division by zero.

    Args:
        numerator: Numerator series
        denominator: Denominator series

    Returns:
        Result of division with EPS added to denominator
    """
    return numerator / (denominator + EPS)


def zscore(series: pd.Series, window: int) -> pd.Series:
    """Compute rolling z-score.

    Args:
        series: Input series
        window: Rolling window size

    Returns:
        Rolling z-score (value - mean) / std
    """
    rolling_mean = series.rolling(window=window, min_periods=window).mean()
    rolling_std = series.rolling(window=window, min_periods=window).std()
    return safe_divide(series - rolling_mean, rolling_std)


def log_return(prices: pd.Series, periods: int = 1) -> pd.Series:
    """Compute log returns.

    Args:
        prices: Price series
        periods: Number of periods to lag

    Returns:
        Log returns: log(price_t / price_{t-periods})
    """
    return np.log(safe_divide(prices, prices.shift(periods)))


def rolling_regression_slope(series: pd.Series, window: int) -> pd.Series:
    """Compute rolling linear regression slope.

    Fits y = a + b*x where x is time index (0, 1, ..., window-1).

    Args:
        series: Input series (e.g., log prices)
        window: Rolling window size

    Returns:
        Series of regression slopes
    """
    def _slope(y: np.ndarray) -> float:
        if len(y) < window or np.any(np.isnan(y)):
            return np.nan
        x = np.arange(len(y))
        x_mean = x.mean()
        y_mean = y.mean()
        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sum((x - x_mean) ** 2)
        if denominator < EPS:
            return 0.0
        return numerator / denominator

    return series.rolling(window=window, min_periods=window).apply(_slope, raw=True)


def ema(series: pd.Series, span: int) -> pd.Series:
    """Compute exponential moving average.

    Args:
        series: Input series
        span: EMA span (number of periods)

    Returns:
        Exponential moving average
    """
    return series.ewm(span=span, adjust=False).mean()


def rolling_beta(
    asset_returns: pd.Series, market_returns: pd.Series, window: int
) -> tuple[pd.Series, pd.Series]:
    """Compute rolling beta and residual volatility from regression.

    Fits: asset_return = alpha + beta * market_return + residual

    Args:
        asset_returns: Asset return series
        market_returns: Market return series
        window: Rolling window size

    Returns:
        Tuple of (beta series, residual volatility series)
    """
    betas = []
    resid_stds = []

    for i in range(len(asset_returns)):
        if i < window - 1:
            betas.append(np.nan)
            resid_stds.append(np.nan)
        else:
            y = asset_returns.iloc[i - window + 1 : i + 1].values
            x = market_returns.iloc[i - window + 1 : i + 1].values

            if np.any(np.isnan(y)) or np.any(np.isnan(x)):
                betas.append(np.nan)
                resid_stds.append(np.nan)
            else:
                x_mean = x.mean()
                y_mean = y.mean()
                cov = np.sum((x - x_mean) * (y - y_mean))
                var = np.sum((x - x_mean) ** 2)

                if var < EPS:
                    betas.append(0.0)
                    resid_stds.append(np.std(y))
                else:
                    beta = cov / var
                    alpha = y_mean - beta * x_mean
                    residuals = y - (alpha + beta * x)
                    betas.append(beta)
                    resid_stds.append(np.std(residuals))

    beta_series = pd.Series(betas, index=asset_returns.index)
    resid_series = pd.Series(resid_stds, index=asset_returns.index)

    return beta_series, resid_series


