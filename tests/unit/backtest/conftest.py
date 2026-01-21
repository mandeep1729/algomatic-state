"""Shared fixtures for backtest tests."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_ohlcv_data() -> dict[str, pd.DataFrame]:
    """Create sample OHLCV data for testing."""
    np.random.seed(42)
    n_bars = 1000

    # Create 1-minute bars
    index = pd.date_range("2024-01-01 09:30", periods=n_bars, freq="1min")

    # Generate price series with trend and noise
    base_price = 100.0
    returns = np.random.randn(n_bars) * 0.001 + 0.00001  # Slight upward bias
    prices = base_price * np.exp(np.cumsum(returns))

    # Generate OHLCV
    close = prices
    high = close * (1 + np.abs(np.random.randn(n_bars)) * 0.002)
    low = close * (1 - np.abs(np.random.randn(n_bars)) * 0.002)
    open_ = close.copy()
    open_[1:] = close[:-1]
    volume = np.random.randint(1000, 10000, n_bars)

    df = pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }, index=index)

    return {"AAPL": df}


@pytest.fixture
def sample_features(sample_ohlcv_data) -> dict[str, pd.DataFrame]:
    """Create sample features from OHLCV data."""
    features = {}
    for symbol, df in sample_ohlcv_data.items():
        feat_df = df.copy()
        # Add simple features
        feat_df["r1"] = np.log(df["close"] / df["close"].shift(1))
        feat_df["r5"] = np.log(df["close"] / df["close"].shift(5))
        feat_df["rv_15"] = feat_df["r1"].rolling(15).std()
        features[symbol] = feat_df.dropna()
    return features


@pytest.fixture
def sample_trades() -> list[dict]:
    """Create sample trades for testing."""
    return [
        {
            "symbol": "AAPL",
            "direction": "long",
            "quantity": 100,
            "entry_price": 100.0,
            "exit_price": 102.0,
            "entry_time": datetime(2024, 1, 1, 10, 0),
            "exit_time": datetime(2024, 1, 1, 11, 0),
            "pnl": 195.0,  # 200 - 5 commission
            "commission": 5.0,
            "slippage": 0.0,
        },
        {
            "symbol": "AAPL",
            "direction": "long",
            "quantity": 100,
            "entry_price": 102.0,
            "exit_price": 101.0,
            "entry_time": datetime(2024, 1, 1, 12, 0),
            "exit_time": datetime(2024, 1, 1, 13, 0),
            "pnl": -105.0,  # -100 - 5 commission
            "commission": 5.0,
            "slippage": 0.0,
        },
        {
            "symbol": "AAPL",
            "direction": "short",
            "quantity": 50,
            "entry_price": 101.0,
            "exit_price": 100.0,
            "entry_time": datetime(2024, 1, 1, 14, 0),
            "exit_time": datetime(2024, 1, 1, 15, 0),
            "pnl": 47.5,  # 50 - 2.5 commission
            "commission": 2.5,
            "slippage": 0.0,
        },
    ]


@pytest.fixture
def sample_equity_curve() -> pd.Series:
    """Create sample equity curve."""
    np.random.seed(42)
    n_points = 500

    index = pd.date_range("2024-01-01", periods=n_points, freq="1h")

    # Generate equity with some drawdowns
    returns = np.random.randn(n_points) * 0.005 + 0.0002
    equity = 100000 * np.exp(np.cumsum(returns))

    return pd.Series(equity, index=index, name="equity")
