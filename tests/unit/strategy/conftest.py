"""Shared fixtures for strategy tests."""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_features() -> pd.DataFrame:
    """Create sample feature DataFrame."""
    np.random.seed(42)
    n_bars = 100

    index = pd.date_range("2024-01-01 09:30", periods=n_bars, freq="1min")

    return pd.DataFrame(
        {
            "r1": np.random.randn(n_bars) * 0.001,
            "r5": np.random.randn(n_bars) * 0.002,
            "r15": np.random.randn(n_bars) * 0.003,
            "rv_15": np.abs(np.random.randn(n_bars)) * 0.01,
            "rv_60": np.abs(np.random.randn(n_bars)) * 0.015,
            "vol_z_60": np.random.randn(n_bars),
        },
        index=index,
    )


@pytest.fixture
def sample_timestamp() -> datetime:
    """Create sample timestamp."""
    return datetime(2024, 1, 1, 10, 30)


@pytest.fixture
def sample_states() -> np.ndarray:
    """Create sample state vectors."""
    np.random.seed(42)
    return np.random.randn(100, 16).astype(np.float32)


@pytest.fixture
def sample_returns() -> np.ndarray:
    """Create sample forward returns."""
    np.random.seed(42)
    return np.random.randn(100).astype(np.float32) * 0.01
