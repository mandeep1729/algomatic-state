"""Tests for HMM scalers."""

import numpy as np
import pytest

from src.hmm.scalers import (
    CombinedScaler,
    FeatureScalerConfig,
    RobustScaler,
    StandardScaler,
    YeoJohnsonScaler,
    create_scaler,
)


class TestRobustScaler:
    """Tests for RobustScaler."""

    def test_fit_transform_basic(self):
        """Test basic fit and transform."""
        X = np.array([[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]])
        scaler = RobustScaler()
        X_scaled = scaler.fit_transform(X)

        assert X_scaled.shape == X.shape
        assert np.allclose(np.nanmedian(X_scaled, axis=0), 0.0, atol=1e-6)

    def test_inverse_transform(self):
        """Test inverse transform recovers original."""
        X = np.array([[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]])
        scaler = RobustScaler(clip_std=None)
        X_scaled = scaler.fit_transform(X)
        X_recovered = scaler.inverse_transform(X_scaled)

        assert np.allclose(X, X_recovered, atol=1e-6)

    def test_clipping(self):
        """Test outlier clipping."""
        X = np.array([[0], [1], [2], [3], [100]])
        scaler = RobustScaler(clip_std=2.0)
        scaler.fit(X)
        X_scaled = scaler.transform(X)

        assert X_scaled.max() <= 2.0
        assert X_scaled.min() >= -2.0

    def test_nan_handling(self):
        """Test that NaN values are preserved."""
        X = np.array([[1, 2], [np.nan, 4], [5, 6]])
        scaler = RobustScaler()
        scaler.fit(X)
        X_scaled = scaler.transform(X)

        assert np.isnan(X_scaled[1, 0])
        assert not np.isnan(X_scaled[1, 1])

    def test_unfitted_raises(self):
        """Test that transform before fit raises error."""
        scaler = RobustScaler()
        with pytest.raises(ValueError, match="not fitted"):
            scaler.transform(np.array([[1, 2]]))


class TestStandardScaler:
    """Tests for StandardScaler."""

    def test_fit_transform_basic(self):
        """Test basic fit and transform."""
        X = np.array([[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]])
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        assert X_scaled.shape == X.shape
        assert np.allclose(np.mean(X_scaled, axis=0), 0.0, atol=1e-6)
        assert np.allclose(np.std(X_scaled, axis=0), 1.0, atol=1e-6)

    def test_inverse_transform(self):
        """Test inverse transform recovers original."""
        X = np.array([[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]])
        scaler = StandardScaler(clip_std=None)
        X_scaled = scaler.fit_transform(X)
        X_recovered = scaler.inverse_transform(X_scaled)

        assert np.allclose(X, X_recovered, atol=1e-6)


class TestYeoJohnsonScaler:
    """Tests for YeoJohnsonScaler."""

    def test_fit_transform_basic(self):
        """Test basic fit and transform."""
        np.random.seed(42)
        X = np.exp(np.random.randn(100, 2))
        scaler = YeoJohnsonScaler()
        X_scaled = scaler.fit_transform(X)

        assert X_scaled.shape == X.shape
        assert scaler.lambdas_ is not None

    def test_transform_shape(self):
        """Test transform preserves shape."""
        X = np.random.randn(50, 3)
        scaler = YeoJohnsonScaler()
        scaler.fit(X)
        X_scaled = scaler.transform(X)

        assert X_scaled.shape == X.shape


class TestCombinedScaler:
    """Tests for CombinedScaler."""

    def test_fit_transform_basic(self):
        """Test basic combined scaling."""
        X = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12], [13, 14, 15]])
        feature_names = ["a", "b", "c"]

        scaler = CombinedScaler(
            feature_names=feature_names,
            default_scaler="robust",
        )
        X_scaled = scaler.fit_transform(X)

        assert X_scaled.shape == X.shape
        assert scaler.fitted_

    def test_per_feature_config(self):
        """Test per-feature configuration."""
        X = np.array([[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]])
        feature_names = ["a", "b"]
        configs = {
            "a": FeatureScalerConfig(scaler_type="robust"),
            "b": FeatureScalerConfig(scaler_type="standard"),
        }

        scaler = CombinedScaler(
            feature_names=feature_names,
            configs=configs,
        )
        X_scaled = scaler.fit_transform(X)

        assert X_scaled.shape == X.shape

    def test_none_scaler(self):
        """Test no scaling option."""
        X = np.array([[1, 2], [3, 4], [5, 6]])
        feature_names = ["a", "b"]
        configs = {
            "a": FeatureScalerConfig(scaler_type="none"),
            "b": FeatureScalerConfig(scaler_type="robust"),
        }

        scaler = CombinedScaler(
            feature_names=feature_names,
            configs=configs,
        )
        X_scaled = scaler.fit_transform(X)

        assert np.array_equal(X_scaled[:, 0], X[:, 0])

    def test_differencing(self):
        """Test differencing for stationarity."""
        X = np.array([[1], [2], [4], [7], [11]])
        feature_names = ["a"]
        configs = {
            "a": FeatureScalerConfig(scaler_type="none", differencing=True),
        }

        scaler = CombinedScaler(
            feature_names=feature_names,
            configs=configs,
        )
        X_scaled = scaler.fit_transform(X)

        expected_diffs = np.array([[0], [1], [2], [3], [4]])
        assert np.allclose(X_scaled, expected_diffs, atol=1e-6)


class TestCreateScaler:
    """Tests for scaler factory function."""

    def test_create_robust(self):
        """Test creating robust scaler."""
        scaler = create_scaler("robust")
        assert isinstance(scaler, RobustScaler)

    def test_create_standard(self):
        """Test creating standard scaler."""
        scaler = create_scaler("standard")
        assert isinstance(scaler, StandardScaler)

    def test_create_yeo_johnson(self):
        """Test creating Yeo-Johnson scaler."""
        scaler = create_scaler("yeo_johnson")
        assert isinstance(scaler, YeoJohnsonScaler)

    def test_invalid_type(self):
        """Test invalid scaler type raises error."""
        with pytest.raises(ValueError, match="Unknown scaler type"):
            create_scaler("invalid")
