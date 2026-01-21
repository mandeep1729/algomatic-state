"""Tests for feature normalization."""

import numpy as np
import pytest

from src.state.normalization import FeatureNormalizer, NormalizationMethod


class TestFeatureNormalizer:
    """Tests for FeatureNormalizer."""

    @pytest.fixture
    def normalizer(self) -> FeatureNormalizer:
        return FeatureNormalizer(method="zscore", clip_value=3.0)

    def test_init(self):
        """Test initialization."""
        norm = FeatureNormalizer(method="robust", clip_value=2.0)
        assert norm.method == NormalizationMethod.ROBUST
        assert norm.clip_value == 2.0
        assert not norm.is_fitted

    def test_fit_zscore(self, sample_windows: np.ndarray):
        """Test fitting with z-score method."""
        norm = FeatureNormalizer(method="zscore")
        norm.fit(sample_windows)
        
        assert norm.is_fitted
        params = norm.get_params()
        assert "mean" in params
        assert "std" in params

    def test_fit_robust(self, sample_windows: np.ndarray):
        """Test fitting with robust method."""
        norm = FeatureNormalizer(method="robust")
        norm.fit(sample_windows)
        
        assert norm.is_fitted
        params = norm.get_params()
        assert "median" in params
        assert "iqr" in params

    def test_transform_zscore(self, sample_windows: np.ndarray):
        """Test z-score normalization."""
        norm = FeatureNormalizer(method="zscore", clip_value=None)
        normalized = norm.fit_transform(sample_windows)
        
        # Check approximate zero mean, unit std per feature
        flat = normalized.reshape(-1, normalized.shape[-1])
        assert np.allclose(flat.mean(axis=0), 0, atol=0.1)
        assert np.allclose(flat.std(axis=0), 1, atol=0.1)

    def test_transform_clipping(self, sample_windows: np.ndarray):
        """Test that clipping works."""
        norm = FeatureNormalizer(method="zscore", clip_value=2.0)
        normalized = norm.fit_transform(sample_windows)
        
        assert normalized.max() <= 2.0
        assert normalized.min() >= -2.0

    def test_inverse_transform(self, sample_windows: np.ndarray):
        """Test inverse transform recovers original."""
        norm = FeatureNormalizer(method="zscore", clip_value=None)
        normalized = norm.fit_transform(sample_windows)
        recovered = norm.inverse_transform(normalized)
        
        assert np.allclose(sample_windows, recovered, atol=1e-5)

    def test_transform_before_fit_raises(self, sample_windows: np.ndarray):
        """Test transform before fit raises error."""
        norm = FeatureNormalizer()
        with pytest.raises(RuntimeError, match="fitted"):
            norm.transform(sample_windows)

    def test_set_params(self):
        """Test setting parameters from saved values."""
        norm1 = FeatureNormalizer(method="zscore")
        norm1.fit(np.random.randn(100, 10))
        params = norm1.get_params()
        
        norm2 = FeatureNormalizer()
        norm2.set_params(params)
        
        assert norm2.is_fitted
        assert np.allclose(norm1._mean, norm2._mean)

    def test_2d_input(self):
        """Test normalizer works with 2D input."""
        data = np.random.randn(100, 10).astype(np.float32)
        norm = FeatureNormalizer()
        normalized = norm.fit_transform(data)
        
        assert normalized.shape == data.shape
