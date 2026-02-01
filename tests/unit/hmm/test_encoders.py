"""Tests for HMM encoders."""

import numpy as np
import pytest

from src.features.state.hmm.encoders import (
    PCAEncoder,
    TemporalPCAEncoder,
    create_encoder,
    create_windows,
    select_latent_dim,
)


class TestPCAEncoder:
    """Tests for PCAEncoder."""

    @pytest.fixture
    def sample_data(self) -> np.ndarray:
        """Generate sample data for testing."""
        np.random.seed(42)
        return np.random.randn(100, 10)

    def test_fit_transform_basic(self, sample_data: np.ndarray):
        """Test basic fit and transform."""
        encoder = PCAEncoder(latent_dim=5)
        Z = encoder.fit_transform(sample_data)

        assert Z.shape == (100, 5)
        assert encoder.latent_dim == 5
        assert encoder.input_dim == 10

    def test_dimensionality_reduction(self, sample_data: np.ndarray):
        """Test that latent dim is less than input dim."""
        encoder = PCAEncoder(latent_dim=3)
        encoder.fit(sample_data)

        assert encoder.latent_dim < encoder.input_dim

    def test_inverse_transform(self, sample_data: np.ndarray):
        """Test inverse transform."""
        encoder = PCAEncoder(latent_dim=8)
        Z = encoder.fit_transform(sample_data)
        X_recon = encoder.inverse_transform(Z)

        assert X_recon.shape == sample_data.shape

    def test_reconstruction_error(self, sample_data: np.ndarray):
        """Test reconstruction error computation."""
        encoder = PCAEncoder(latent_dim=8)
        encoder.fit(sample_data)
        errors = encoder.reconstruction_error(sample_data)

        assert errors.shape == (100,)
        assert np.all(errors >= 0)

    def test_metrics_computed(self, sample_data: np.ndarray):
        """Test that metrics are computed after fit."""
        encoder = PCAEncoder(latent_dim=5)
        encoder.fit(sample_data)

        assert encoder.metrics_ is not None
        assert encoder.metrics_.total_variance_explained > 0
        assert len(encoder.metrics_.explained_variance_ratio) == 5

    def test_nan_handling(self):
        """Test handling of NaN values."""
        X = np.random.randn(100, 5)
        X[0, 0] = np.nan
        X[50, 2] = np.nan

        encoder = PCAEncoder(latent_dim=3)
        encoder.fit(X)
        Z = encoder.transform(X)

        assert np.isnan(Z[0]).all()
        assert np.isnan(Z[50]).all()
        assert not np.isnan(Z[1]).any()

    def test_components_property(self, sample_data: np.ndarray):
        """Test components property returns loadings."""
        encoder = PCAEncoder(latent_dim=5)
        encoder.fit(sample_data)

        assert encoder.components.shape == (5, 10)

    def test_explained_variance_ratio(self, sample_data: np.ndarray):
        """Test explained variance ratio property."""
        encoder = PCAEncoder(latent_dim=5)
        encoder.fit(sample_data)

        assert len(encoder.explained_variance_ratio) == 5
        assert np.all(encoder.explained_variance_ratio > 0)
        assert np.all(encoder.explained_variance_ratio <= 1)

    def test_unfitted_raises(self):
        """Test that transform before fit raises error."""
        encoder = PCAEncoder(latent_dim=5)
        with pytest.raises(ValueError, match="not fitted"):
            encoder.transform(np.random.randn(10, 5))


class TestTemporalPCAEncoder:
    """Tests for TemporalPCAEncoder."""

    @pytest.fixture
    def windowed_data(self) -> np.ndarray:
        """Generate windowed sample data."""
        np.random.seed(42)
        return np.random.randn(100, 5, 8)

    def test_fit_transform_basic(self, windowed_data: np.ndarray):
        """Test basic fit and transform."""
        encoder = TemporalPCAEncoder(latent_dim=6, window_size=5)
        Z = encoder.fit_transform(windowed_data)

        assert Z.shape == (100, 6)
        assert encoder.window_size == 5
        assert encoder.feature_dim == 8

    def test_inverse_transform(self, windowed_data: np.ndarray):
        """Test inverse transform."""
        encoder = TemporalPCAEncoder(latent_dim=10, window_size=5)
        Z = encoder.fit_transform(windowed_data)
        X_recon = encoder.inverse_transform(Z)

        assert X_recon.shape == windowed_data.shape

    def test_window_size_mismatch(self):
        """Test that mismatched window size raises error."""
        encoder = TemporalPCAEncoder(latent_dim=5, window_size=5)
        X = np.random.randn(50, 3, 8)

        with pytest.raises(ValueError, match="Window size mismatch"):
            encoder.fit(X)


class TestCreateWindows:
    """Tests for create_windows utility."""

    def test_basic_windowing(self):
        """Test basic window creation."""
        X = np.arange(20).reshape(10, 2)
        windows = create_windows(X, window_size=3, stride=1)

        assert windows.shape == (8, 3, 2)
        assert np.array_equal(windows[0], X[0:3])
        assert np.array_equal(windows[1], X[1:4])

    def test_stride(self):
        """Test windowing with stride > 1."""
        X = np.arange(20).reshape(10, 2)
        windows = create_windows(X, window_size=3, stride=2)

        assert windows.shape == (4, 3, 2)
        assert np.array_equal(windows[0], X[0:3])
        assert np.array_equal(windows[1], X[2:5])

    def test_window_too_large(self):
        """Test that large window raises error."""
        X = np.random.randn(5, 3)

        with pytest.raises(ValueError, match="Window size"):
            create_windows(X, window_size=10)


class TestSelectLatentDim:
    """Tests for select_latent_dim utility."""

    def test_basic_selection(self):
        """Test basic latent dimension selection."""
        np.random.seed(42)
        X = np.random.randn(200, 10)

        dim = select_latent_dim(X, variance_threshold=0.95)
        assert 2 <= dim <= 10

    def test_respects_bounds(self):
        """Test that selection respects min/max bounds."""
        np.random.seed(42)
        X = np.random.randn(200, 20)

        dim = select_latent_dim(X, max_dim=5, min_dim=3)
        assert 3 <= dim <= 5


class TestCreateEncoder:
    """Tests for encoder factory function."""

    def test_create_pca(self):
        """Test creating PCA encoder."""
        encoder = create_encoder("pca", latent_dim=5)
        assert isinstance(encoder, PCAEncoder)
        assert encoder.latent_dim == 5

    def test_create_temporal_pca(self):
        """Test creating temporal PCA encoder."""
        encoder = create_encoder("temporal_pca", latent_dim=5, window_size=3)
        assert isinstance(encoder, TemporalPCAEncoder)
        assert encoder.window_size == 3

    def test_invalid_type(self):
        """Test invalid encoder type raises error."""
        with pytest.raises(ValueError, match="Unknown encoder type"):
            create_encoder("invalid")
