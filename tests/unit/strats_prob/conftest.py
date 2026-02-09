"""Shared fixtures for strategy probe tests."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def probe_ohlcv_df() -> pd.DataFrame:
    """Create OHLCV + indicator data suitable for probe engine testing.

    Returns 200 bars with OHLCV data plus pre-computed indicator columns
    that strategies reference (ema_20, ema_50, atr_14, rsi_14, etc.).
    """
    np.random.seed(42)
    n_bars = 200

    base_date = pd.Timestamp("2024-06-03 09:30:00")
    index = pd.date_range(start=base_date, periods=n_bars, freq="1h")

    # Generate trending close prices with noise
    trend = np.linspace(100, 115, n_bars)
    noise = np.random.randn(n_bars) * 0.3
    close = trend + noise

    open_prices = np.roll(close, 1) + np.random.randn(n_bars) * 0.08
    open_prices[0] = close[0] - 0.1

    high = np.maximum(open_prices, close) + np.abs(np.random.randn(n_bars)) * 0.25
    low = np.minimum(open_prices, close) - np.abs(np.random.randn(n_bars)) * 0.25
    volume = np.maximum((10000 + np.random.randn(n_bars) * 2000).astype(int), 100)

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

    # Add indicator columns that strategies commonly reference
    df["ema_20"] = df["close"].ewm(span=20).mean()
    df["ema_50"] = df["close"].ewm(span=50).mean()
    df["ema_200"] = df["close"].ewm(span=200).mean()
    df["sma_20"] = df["close"].rolling(20).mean()
    df["sma_50"] = df["close"].rolling(50).mean()
    df["sma_200"] = df["close"].rolling(200).mean()

    # ATR
    tr = np.maximum(
        df["high"] - df["low"],
        np.maximum(
            abs(df["high"] - df["close"].shift(1)),
            abs(df["low"] - df["close"].shift(1)),
        ),
    )
    df["atr_14"] = tr.rolling(14).mean()

    # RSI
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi_14"] = 100 - (100 / (1 + rs))

    # Bollinger Bands
    df["bb_middle"] = df["sma_20"]
    bb_std = df["close"].rolling(20).std()
    df["bb_upper"] = df["bb_middle"] + 2 * bb_std
    df["bb_lower"] = df["bb_middle"] - 2 * bb_std
    df["bb_width"] = df["bb_upper"] - df["bb_lower"]

    # MACD
    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # Stochastic
    low_14 = df["low"].rolling(14).min()
    high_14 = df["high"].rolling(14).max()
    df["stoch_k"] = 100 * (df["close"] - low_14) / (high_14 - low_14).replace(0, np.nan)
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()

    # ADX (simplified)
    df["adx_14"] = pd.Series(np.linspace(15, 30, n_bars), index=index)

    # Simple additional indicators
    df["obv"] = (np.sign(df["close"].diff()) * df["volume"]).cumsum()
    df["psar"] = df["close"] - 0.5  # Simplified: SAR below close
    df["willr_14"] = -50.0  # Neutral placeholder
    df["cci_20"] = 0.0  # Neutral placeholder
    df["mfi_14"] = 50.0  # Neutral placeholder

    return df


@pytest.fixture
def simple_long_signal_df() -> pd.DataFrame:
    """Create a DataFrame with a clear long entry signal for EMA cross.

    EMA20 crosses above EMA50 at a specific bar to test entry logic.
    """
    n_bars = 30
    base_date = pd.Timestamp("2024-06-03 09:30:00")
    index = pd.date_range(start=base_date, periods=n_bars, freq="1h")

    close = np.array([
        # Bars 0-9: EMA20 < EMA50 (no signal)
        100.0, 100.1, 100.0, 99.9, 100.0, 100.1, 100.0, 99.9, 100.0, 100.1,
        # Bars 10-14: EMA20 rises above EMA50 (signal around bar 12)
        100.5, 101.0, 101.5, 102.0, 102.5,
        # Bars 15-24: continues up then reverses
        103.0, 103.5, 103.0, 102.5, 102.0,
        101.5, 101.0, 100.5, 100.0, 99.5,
        # Bars 25-29: continues down
        99.0, 98.5, 98.0, 97.5, 97.0,
    ])

    open_prices = np.roll(close, 1)
    open_prices[0] = close[0]
    high = np.maximum(open_prices, close) + 0.2
    low = np.minimum(open_prices, close) - 0.2
    volume = np.full(n_bars, 10000)

    df = pd.DataFrame(
        {"open": open_prices, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )

    # Compute EMAs
    df["ema_20"] = df["close"].ewm(span=20).mean()
    df["ema_50"] = df["close"].ewm(span=50).mean()

    # ATR (constant for simplicity)
    df["atr_14"] = 0.5

    return df
