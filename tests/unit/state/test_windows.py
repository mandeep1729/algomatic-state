"""Tests for window generation."""

import numpy as np
import pandas as pd
import pytest

from src.state.windows import WindowGenerator


class TestWindowGenerator:
    """Tests for WindowGenerator."""

    @pytest.fixture
    def generator(self) -> WindowGenerator:
        return WindowGenerator(window_size=20, stride=1)

    def test_init(self):
        """Test initialization with parameters."""
        gen = WindowGenerator(window_size=60, stride=5)
        assert gen.window_size == 60
        assert gen.stride == 5

    def test_config(self, generator: WindowGenerator):
        """Test config property."""
        config = generator.config
        assert config.window_size == 20
        assert config.stride == 1

    def test_generate_shape(self, generator: WindowGenerator, sample_features_df: pd.DataFrame):
        """Test output shape of generate."""
        windows, timestamps = generator.generate(sample_features_df)
        
        n_expected = (len(sample_features_df) - 20) // 1 + 1
        assert windows.shape == (n_expected, 20, 10)
        assert len(timestamps) == n_expected

    def test_generate_stride(self, sample_features_df: pd.DataFrame):
        """Test stride affects number of windows."""
        gen1 = WindowGenerator(window_size=20, stride=1)
        gen5 = WindowGenerator(window_size=20, stride=5)
        
        windows1, _ = gen1.generate(sample_features_df)
        windows5, _ = gen5.generate(sample_features_df)
        
        assert len(windows5) < len(windows1)

    def test_generate_timestamps(self, generator: WindowGenerator, sample_features_df: pd.DataFrame):
        """Test timestamp alignment."""
        windows, timestamps = generator.generate(sample_features_df)
        
        # First timestamp should be at index window_size - 1
        assert timestamps[0] == sample_features_df.index[19]
        # Last timestamp should be at end
        assert timestamps[-1] == sample_features_df.index[-1]

    def test_generate_insufficient_data(self):
        """Test error on insufficient data."""
        gen = WindowGenerator(window_size=100)
        df = pd.DataFrame(np.random.randn(50, 5), index=pd.date_range("2024-01-01", periods=50, freq="1min"))
        
        with pytest.raises(ValueError, match="window_size"):
            gen.generate(df)

    def test_generate_single(self, generator: WindowGenerator, sample_features_df: pd.DataFrame):
        """Test generating single window."""
        window = generator.generate_single(sample_features_df)
        
        assert window.shape == (20, 10)
        assert np.allclose(window, sample_features_df.iloc[-20:].values)

    def test_flatten_unflatten(self, generator: WindowGenerator, sample_windows: np.ndarray):
        """Test flatten and unflatten are inverse."""
        flat = generator.flatten_windows(sample_windows)
        unflat = generator.unflatten_windows(flat, n_features=10)
        
        assert np.allclose(sample_windows, unflat)
