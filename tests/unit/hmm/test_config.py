"""Tests for HMM configuration."""

import tempfile
from pathlib import Path

import pytest
import yaml

from src.hmm.config import (
    DEFAULT_FEATURE_SET,
    FeatureSpecEntry,
    StateVectorConfig,
    StateVectorFeatureSpec,
    TimeframeConfig,
    create_default_config,
    load_feature_spec,
    save_config,
)


class TestFeatureSpecEntry:
    """Tests for FeatureSpecEntry."""

    def test_defaults(self):
        """Test default values."""
        entry = FeatureSpecEntry(name="r5")

        assert entry.name == "r5"
        assert entry.scaling == "robust"
        assert entry.differencing is False
        assert entry.clip_std == 5.0

    def test_custom_values(self):
        """Test custom values."""
        entry = FeatureSpecEntry(
            name="vol",
            description="Volatility",
            lookback=60,
            scaling="standard",
            differencing=True,
        )

        assert entry.lookback == 60
        assert entry.scaling == "standard"
        assert entry.differencing is True


class TestTimeframeConfig:
    """Tests for TimeframeConfig."""

    def test_defaults(self):
        """Test default values."""
        config = TimeframeConfig()

        assert config.n_states == 8
        assert config.latent_dim == 8
        assert config.covariance_type == "diag"
        assert config.min_dwell_bars == 3
        assert config.p_switch_threshold == 0.6

    def test_validation(self):
        """Test validation constraints."""
        with pytest.raises(ValueError):
            TimeframeConfig(n_states=1)

        with pytest.raises(ValueError):
            TimeframeConfig(p_switch_threshold=0.4)


class TestStateVectorConfig:
    """Tests for StateVectorConfig."""

    def test_defaults(self):
        """Test default values."""
        config = StateVectorConfig()

        assert config.encoder_type == "pca"
        assert config.scaler_type == "robust"
        assert len(config.base_features) == len(DEFAULT_FEATURE_SET)

    def test_get_timeframe_config(self):
        """Test getting timeframe-specific config."""
        config = StateVectorConfig(
            timeframe_configs={
                "1Min": TimeframeConfig(n_states=12),
            }
        )

        tf_config = config.get_timeframe_config("1Min")
        assert tf_config.n_states == 12

        default_config = config.get_timeframe_config("5Min")
        assert default_config.n_states == 8

    def test_invalid_timeframe(self):
        """Test invalid timeframe raises error."""
        config = StateVectorConfig()

        with pytest.raises(ValueError, match="Invalid timeframe"):
            config.get_timeframe_config("2Min")

    def test_get_features_for_timeframe(self):
        """Test getting features for timeframe with overrides."""
        config = StateVectorConfig(
            base_features=["a", "b", "c"],
            timeframe_configs={
                "1Min": TimeframeConfig(
                    features_include=["d"],
                    features_exclude=["b"],
                ),
            }
        )

        features = config.get_features_for_timeframe("1Min")

        assert "a" in features
        assert "b" not in features
        assert "c" in features
        assert "d" in features

    def test_feature_budget(self):
        """Test feature budget limit."""
        config = StateVectorConfig(
            base_features=["a", "b", "c", "d", "e"],
            timeframe_configs={
                "1Min": TimeframeConfig(feature_budget=3),
            }
        )

        features = config.get_features_for_timeframe("1Min")

        assert len(features) == 3


class TestCreateDefaultConfig:
    """Tests for create_default_config."""

    def test_creates_valid_config(self):
        """Test default config is valid."""
        config = create_default_config()

        assert isinstance(config, StateVectorConfig)
        assert "1Min" in config.timeframe_configs
        assert "1Day" in config.timeframe_configs


class TestSaveConfig:
    """Tests for save_config."""

    def test_save_and_load(self):
        """Test config round-trip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StateVectorConfig(
                encoder_type="pca",
                base_features=["r5", "vol"],
            )
            path = Path(tmpdir) / "config.yaml"

            save_config(config, path)

            assert path.exists()

            with open(path) as f:
                loaded = yaml.safe_load(f)

            assert loaded["encoder_type"] == "pca"
            assert loaded["base_features"] == ["r5", "vol"]


class TestLoadFeatureSpec:
    """Tests for load_feature_spec."""

    def test_load_from_file(self):
        """Test loading feature spec from YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_content = {
                "encoder_type": "pca",
                "base_features": ["r5", "vol", "macd"],
                "timeframe_configs": {
                    "1Min": {
                        "n_states": 10,
                        "latent_dim": 8,
                    }
                },
            }
            path = Path(tmpdir) / "config.yaml"
            with open(path, "w") as f:
                yaml.dump(config_content, f)

            spec = load_feature_spec(path, "1Min")

            assert spec.timeframe == "1Min"
            assert len(spec.features) == 3
            assert spec.config.encoder_type == "pca"

    def test_file_not_found(self):
        """Test error when file not found."""
        with pytest.raises(FileNotFoundError):
            load_feature_spec(Path("/nonexistent/path.yaml"), "1Min")


class TestStateVectorFeatureSpec:
    """Tests for StateVectorFeatureSpec."""

    def test_properties(self):
        """Test feature spec properties."""
        features = [
            FeatureSpecEntry(name="a", lookback=5),
            FeatureSpecEntry(name="b", lookback=10),
            FeatureSpecEntry(name="c", lookback=3),
        ]
        spec = StateVectorFeatureSpec(
            features=features,
            timeframe="1Min",
            config=StateVectorConfig(),
        )

        assert spec.feature_names == ["a", "b", "c"]
        assert spec.max_lookback == 10

    def test_get_feature(self):
        """Test getting feature by name."""
        features = [
            FeatureSpecEntry(name="a"),
            FeatureSpecEntry(name="b"),
        ]
        spec = StateVectorFeatureSpec(
            features=features,
            timeframe="1Min",
            config=StateVectorConfig(),
        )

        feature = spec.get_feature("a")
        assert feature is not None
        assert feature.name == "a"

        missing = spec.get_feature("nonexistent")
        assert missing is None
