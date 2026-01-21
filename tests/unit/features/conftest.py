"""Shared fixtures for feature engineering tests."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def ohlcv_df() -> pd.DataFrame:
    """Create sample OHLCV data for testing.

    Returns 100 bars of synthetic minute data with realistic properties:
    - Trending close prices with noise
    - High >= max(open, close), Low <= min(open, close)
    - Positive volume with variation

    Returns:
        DataFrame with datetime index and columns: open, high, low, close, volume
    """
    np.random.seed(42)
    n_bars = 100

    # Create datetime index (1-minute bars during trading hours)
    base_date = pd.Timestamp("2024-01-15 09:30:00")
    index = pd.date_range(start=base_date, periods=n_bars, freq="1min")

    # Generate trending close prices with noise
    trend = np.linspace(100, 105, n_bars)
    noise = np.random.randn(n_bars) * 0.5
    close = trend + noise

    # Generate open prices (slightly offset from previous close)
    open_prices = np.roll(close, 1) + np.random.randn(n_bars) * 0.1
    open_prices[0] = close[0] - 0.1

    # Generate high/low to ensure consistency
    high = np.maximum(open_prices, close) + np.abs(np.random.randn(n_bars)) * 0.3
    low = np.minimum(open_prices, close) - np.abs(np.random.randn(n_bars)) * 0.3

    # Generate volume with variation
    base_volume = 10000
    volume = (base_volume + np.random.randn(n_bars) * 2000).astype(int)
    volume = np.maximum(volume, 100)  # Ensure positive

    df = pd.DataFrame(
        {
            "open": open_prices,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=index,
    )

    return df


@pytest.fixture
def market_df(ohlcv_df: pd.DataFrame) -> pd.DataFrame:
    """Create sample market (SPY-like) data for testing.

    Generates market data that is correlated with the asset data
    but with different scale and noise.

    Args:
        ohlcv_df: Asset OHLCV data (used for index alignment)

    Returns:
        DataFrame with datetime index and columns: open, high, low, close, volume
    """
    np.random.seed(123)
    n_bars = len(ohlcv_df)

    # Generate market close correlated with asset but different scale
    market_trend = np.linspace(450, 455, n_bars)
    market_noise = np.random.randn(n_bars) * 1.0
    close = market_trend + market_noise

    # Generate other OHLCV fields
    open_prices = np.roll(close, 1) + np.random.randn(n_bars) * 0.2
    open_prices[0] = close[0] - 0.2

    high = np.maximum(open_prices, close) + np.abs(np.random.randn(n_bars)) * 0.5
    low = np.minimum(open_prices, close) - np.abs(np.random.randn(n_bars)) * 0.5

    volume = (50000 + np.random.randn(n_bars) * 10000).astype(int)
    volume = np.maximum(volume, 1000)

    df = pd.DataFrame(
        {
            "open": open_prices,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=ohlcv_df.index,
    )

    return df


@pytest.fixture
def small_ohlcv_df() -> pd.DataFrame:
    """Create a small OHLCV dataset for edge case testing.

    Returns:
        DataFrame with 10 bars
    """
    np.random.seed(99)
    n_bars = 10

    base_date = pd.Timestamp("2024-01-15 09:30:00")
    index = pd.date_range(start=base_date, periods=n_bars, freq="1min")

    close = np.array([100.0, 100.5, 101.0, 100.8, 101.2, 101.5, 101.3, 101.8, 102.0, 102.2])
    open_prices = np.array([99.9, 100.0, 100.5, 101.0, 100.7, 101.2, 101.6, 101.2, 101.8, 102.0])
    high = np.maximum(open_prices, close) + 0.2
    low = np.minimum(open_prices, close) - 0.2
    volume = np.array([10000, 12000, 8000, 15000, 11000, 9000, 13000, 10000, 14000, 11000])

    return pd.DataFrame(
        {
            "open": open_prices,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=index,
    )
