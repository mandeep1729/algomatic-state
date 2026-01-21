"""Tests for PCA state extraction."""

import numpy as np
import pytest

from src.state.pca import PCAStateExtractor


class TestPCAStateExtractor:
    """Tests for PCAStateExtractor."""

    @pytest.fixture
    def extractor(self) -> PCAStateExtractor:
        return PCAStateExtractor(n_components=4)

    def test_init(self):
        """Test initialization."""
        ext = PCAStateExtractor(n_components=8, whiten=True)
        assert ext.n_components == 8
        assert ext.whiten
        assert not ext.is_fitted

    def test_fit(self, extractor: PCAStateExtractor, sample_windows: np.ndarray):
        """Test fitting PCA."""
        extractor.fit(sample_windows)
        
        assert extractor.is_fitted
        assert extractor.n_components_fitted == 4

    def test_transform_shape(self, extractor: PCAStateExtractor, sample_windows: np.ndarray):
        """Test output shape of transform."""
        states = extractor.fit_transform(sample_windows)
        
        assert states.shape == (50, 4)  # 50 samples, 4 components

    def test_explained_variance(self, extractor: PCAStateExtractor, sample_windows: np.ndarray):
        """Test explained variance is computed."""
        extractor.fit(sample_windows)
        
        assert extractor.explained_variance_ratio is not None
        assert len(extractor.explained_variance_ratio) == 4
        assert extractor.total_explained_variance > 0

    def test_inverse_transform(self, extractor: PCAStateExtractor, sample_windows: np.ndarray):
        """Test inverse transform."""
        states = extractor.fit_transform(sample_windows)
        reconstructed = extractor.inverse_transform(states)
        
        # Reconstructed should have same flat shape
        flat_original = sample_windows.reshape(50, -1)
        assert reconstructed.shape == flat_original.shape

    def test_component_importance(self, extractor: PCAStateExtractor, sample_windows: np.ndarray):
        """Test component importance ranking."""
        extractor.fit(sample_windows)
        importance = extractor.get_component_importance()
        
        assert len(importance) == 4
        # First should have highest variance
        assert importance[0][1] >= importance[1][1]

    def test_variance_ratio_components(self, sample_windows: np.ndarray):
        """Test using variance ratio for n_components."""
        ext = PCAStateExtractor(n_components=0.9)  # 90% variance
        ext.fit(sample_windows)
        
        assert ext.total_explained_variance >= 0.9

    def test_transform_before_fit_raises(self, extractor: PCAStateExtractor, sample_windows: np.ndarray):
        """Test transform before fit raises error."""
        with pytest.raises(RuntimeError, match="fitted"):
            extractor.transform(sample_windows)

    def test_2d_input(self):
        """Test extractor works with already-flat 2D input."""
        data = np.random.randn(100, 50).astype(np.float32)
        ext = PCAStateExtractor(n_components=5)
        states = ext.fit_transform(data)
        
        assert states.shape == (100, 5)
