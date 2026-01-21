"""Shared fixtures for state module tests."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_features_df() -> pd.DataFrame:
    """Create sample feature DataFrame for testing.

    Returns:
        DataFrame with 100 rows and 10 features
    """
    np.random.seed(42)
    n_samples = 100
    n_features = 10

    base_date = pd.Timestamp("2024-01-15 09:30:00")
    index = pd.date_range(start=base_date, periods=n_samples, freq="1min")

    data = np.random.randn(n_samples, n_features) * 0.1
    columns = [f"feature_{i}" for i in range(n_features)]

    return pd.DataFrame(data, index=index, columns=columns)


@pytest.fixture
def sample_windows() -> np.ndarray:
    """Create sample windows for testing.

    Returns:
        Array of shape (50, 20, 10) - 50 windows, 20 time steps, 10 features
    """
    np.random.seed(42)
    return np.random.randn(50, 20, 10).astype(np.float32)


@pytest.fixture
def sample_states() -> np.ndarray:
    """Create sample state vectors for testing.

    Returns:
        Array of shape (100, 8) - 100 samples, 8 latent dimensions
    """
    np.random.seed(42)
    return np.random.randn(100, 8).astype(np.float32)


@pytest.fixture
def sample_returns() -> np.ndarray:
    """Create sample forward returns for testing.

    Returns:
        Array of shape (100,) with simulated returns
    """
    np.random.seed(42)
    return np.random.randn(100) * 0.01
