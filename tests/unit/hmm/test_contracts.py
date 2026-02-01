"""Tests for HMM data contracts."""

from datetime import datetime, timezone

import numpy as np
import pytest

from src.features.state.hmm.contracts import (
    FeatureVector,
    HMMOutput,
    LatentStateVector,
    ModelMetadata,
    VALID_TIMEFRAMES,
)


class TestFeatureVector:
    """Tests for FeatureVector dataclass."""

    def test_valid_creation(self):
        """Test creating a valid FeatureVector."""
        fv = FeatureVector(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            timeframe="1Min",
            features={"r5": 0.01, "vol": 0.02},
        )
        assert fv.symbol == "AAPL"
        assert fv.timeframe == "1Min"
        assert fv.features["r5"] == 0.01
        assert not fv.has_gap

    def test_invalid_timeframe(self):
        """Test that invalid timeframe raises ValueError."""
        with pytest.raises(ValueError, match="Invalid timeframe"):
            FeatureVector(
                symbol="AAPL",
                timestamp=datetime.now(timezone.utc),
                timeframe="2Min",
                features={},
            )

    def test_to_array(self):
        """Test conversion to numpy array."""
        fv = FeatureVector(
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            timeframe="1Min",
            features={"a": 1.0, "b": 2.0, "c": 3.0},
        )
        arr = fv.to_array(["a", "c"])
        assert np.array_equal(arr, np.array([1.0, 3.0]))

    def test_to_array_missing_feature(self):
        """Test that missing feature raises KeyError."""
        fv = FeatureVector(
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            timeframe="1Min",
            features={"a": 1.0},
        )
        with pytest.raises(KeyError):
            fv.to_array(["a", "missing"])

    def test_feature_names(self):
        """Test feature_names property returns sorted list."""
        fv = FeatureVector(
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            timeframe="1Min",
            features={"z": 1.0, "a": 2.0, "m": 3.0},
        )
        assert fv.feature_names == ["a", "m", "z"]


class TestLatentStateVector:
    """Tests for LatentStateVector dataclass."""

    def test_valid_creation(self):
        """Test creating a valid LatentStateVector."""
        lsv = LatentStateVector(
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            timeframe="1Min",
            z=np.array([1.0, 2.0, 3.0]),
        )
        assert lsv.latent_dim == 3
        assert lsv.z.shape == (3,)

    def test_list_conversion(self):
        """Test that list input is converted to numpy array."""
        lsv = LatentStateVector(
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            timeframe="1Min",
            z=[1.0, 2.0, 3.0],
        )
        assert isinstance(lsv.z, np.ndarray)

    def test_invalid_z_shape(self):
        """Test that 2D z raises ValueError."""
        with pytest.raises(ValueError, match="1D array"):
            LatentStateVector(
                symbol="AAPL",
                timestamp=datetime.now(timezone.utc),
                timeframe="1Min",
                z=np.array([[1.0, 2.0], [3.0, 4.0]]),
            )


class TestHMMOutput:
    """Tests for HMMOutput dataclass."""

    def test_valid_creation(self):
        """Test creating a valid HMMOutput."""
        posterior = np.array([0.1, 0.7, 0.2])
        output = HMMOutput(
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            timeframe="1Min",
            model_id="state_v001",
            state_id=1,
            state_prob=0.7,
            posterior=posterior,
            log_likelihood=-10.5,
        )
        assert output.n_states == 3
        assert output.state_id == 1

    def test_entropy_calculation(self):
        """Test entropy property."""
        uniform = np.array([0.25, 0.25, 0.25, 0.25])
        output = HMMOutput(
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            timeframe="1Min",
            model_id="state_v001",
            state_id=0,
            state_prob=0.25,
            posterior=uniform,
            log_likelihood=-10.0,
        )
        expected_entropy = -np.sum(uniform * np.log(uniform))
        assert np.isclose(output.entropy, expected_entropy)

    def test_unknown_state(self):
        """Test creating UNKNOWN state for OOD."""
        output = HMMOutput.unknown(
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            timeframe="1Min",
            model_id="state_v001",
            n_states=5,
            log_likelihood=-100.0,
        )
        assert output.state_id == HMMOutput.UNKNOWN_STATE
        assert output.is_ood
        assert output.n_states == 5
        assert np.isclose(output.state_prob, 0.2)


class TestModelMetadata:
    """Tests for ModelMetadata dataclass."""

    @pytest.fixture
    def valid_metadata(self) -> ModelMetadata:
        """Create valid metadata fixture."""
        return ModelMetadata(
            model_id="state_v001",
            timeframe="1Min",
            version="1.0.0",
            created_at=datetime.now(timezone.utc),
            training_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            training_end=datetime(2024, 6, 30, tzinfo=timezone.utc),
            n_states=8,
            latent_dim=10,
            feature_names=["r5", "vol"],
            symbols=["AAPL", "MSFT"],
        )

    def test_valid_creation(self, valid_metadata: ModelMetadata):
        """Test creating valid metadata."""
        assert valid_metadata.model_id == "state_v001"
        assert valid_metadata.n_states == 8

    def test_invalid_n_states(self):
        """Test that n_states < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_states"):
            ModelMetadata(
                model_id="state_v001",
                timeframe="1Min",
                version="1.0.0",
                created_at=datetime.now(timezone.utc),
                training_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                training_end=datetime(2024, 6, 30, tzinfo=timezone.utc),
                n_states=1,
                latent_dim=10,
                feature_names=[],
                symbols=[],
            )

    def test_to_dict_and_back(self, valid_metadata: ModelMetadata):
        """Test round-trip serialization."""
        d = valid_metadata.to_dict()
        restored = ModelMetadata.from_dict(d)
        assert restored.model_id == valid_metadata.model_id
        assert restored.n_states == valid_metadata.n_states
        assert restored.feature_names == valid_metadata.feature_names


class TestValidTimeframes:
    """Tests for valid timeframes constant."""

    def test_all_timeframes_present(self):
        """Test all expected timeframes are in the set."""
        expected = {"1Min", "5Min", "15Min", "1Hour", "1Day"}
        assert VALID_TIMEFRAMES == expected
