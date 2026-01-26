"""Tests for HMM artifact management."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.hmm.artifacts import (
    ArtifactPaths,
    StatesPaths,
    generate_model_id,
    get_latest_model,
    get_model_path,
    get_states_path,
    list_models,
)
from src.hmm.contracts import ModelMetadata


class TestArtifactPaths:
    """Tests for ArtifactPaths."""

    def test_basic_paths(self):
        """Test basic path generation."""
        paths = ArtifactPaths(
            root=Path("models"),
            timeframe="1Min",
            model_id="state_v001",
        )

        assert paths.model_dir == Path("models/timeframe=1Min/model_id=state_v001")
        assert paths.scaler_path == Path("models/timeframe=1Min/model_id=state_v001/scaler.pkl")
        assert paths.encoder_path == Path("models/timeframe=1Min/model_id=state_v001/encoder.pkl")
        assert paths.hmm_path == Path("models/timeframe=1Min/model_id=state_v001/hmm.pkl")
        assert paths.metadata_path == Path("models/timeframe=1Min/model_id=state_v001/metadata.json")

    def test_invalid_timeframe(self):
        """Test that invalid timeframe raises error."""
        with pytest.raises(ValueError, match="Invalid timeframe"):
            ArtifactPaths(
                root=Path("models"),
                timeframe="2Min",
                model_id="state_v001",
            )

    def test_ensure_dirs(self):
        """Test directory creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = ArtifactPaths(
                root=Path(tmpdir),
                timeframe="1Min",
                model_id="state_v001",
            )
            paths.ensure_dirs()

            assert paths.model_dir.exists()

    def test_exists_false_when_empty(self):
        """Test exists returns False when no artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = ArtifactPaths(
                root=Path(tmpdir),
                timeframe="1Min",
                model_id="state_v001",
            )
            assert not paths.exists()

    def test_save_load_metadata(self):
        """Test metadata round-trip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = ArtifactPaths(
                root=Path(tmpdir),
                timeframe="1Min",
                model_id="state_v001",
            )

            metadata = ModelMetadata(
                model_id="state_v001",
                timeframe="1Min",
                version="1.0.0",
                created_at=datetime.now(timezone.utc),
                training_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                training_end=datetime(2024, 6, 30, tzinfo=timezone.utc),
                n_states=8,
                latent_dim=10,
                feature_names=["r5", "vol"],
                symbols=["AAPL"],
            )

            paths.save_metadata(metadata)
            loaded = paths.load_metadata()

            assert loaded.model_id == metadata.model_id
            assert loaded.n_states == metadata.n_states
            assert loaded.feature_names == metadata.feature_names


class TestStatesPaths:
    """Tests for StatesPaths."""

    def test_basic_paths(self):
        """Test basic state path generation."""
        paths = StatesPaths(
            root=Path("states"),
            timeframe="1Min",
            model_id="state_v001",
        )

        assert paths.base_dir == Path("states/timeframe=1Min/model_id=state_v001")
        assert paths.get_symbol_dir("AAPL") == Path(
            "states/timeframe=1Min/model_id=state_v001/symbol=AAPL"
        )

    def test_parquet_path(self):
        """Test parquet file path generation."""
        paths = StatesPaths(
            root=Path("states"),
            timeframe="1Min",
            model_id="state_v001",
        )
        date = datetime(2024, 1, 15)

        parquet_path = paths.get_parquet_path("AAPL", date)

        assert parquet_path == Path(
            "states/timeframe=1Min/model_id=state_v001/symbol=AAPL/date=2024-01-15/data.parquet"
        )

    def test_list_symbols_empty(self):
        """Test list_symbols when empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = StatesPaths(
                root=Path(tmpdir),
                timeframe="1Min",
                model_id="state_v001",
            )

            symbols = paths.list_symbols()
            assert symbols == []

    def test_list_symbols(self):
        """Test list_symbols with existing data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = StatesPaths(
                root=Path(tmpdir),
                timeframe="1Min",
                model_id="state_v001",
            )

            (paths.base_dir / "symbol=AAPL").mkdir(parents=True)
            (paths.base_dir / "symbol=MSFT").mkdir(parents=True)

            symbols = paths.list_symbols()
            assert symbols == ["AAPL", "MSFT"]


class TestGenerateModelId:
    """Tests for model ID generation."""

    def test_basic_generation(self):
        """Test basic model ID generation."""
        model_id = generate_model_id(prefix="state", version=1)
        assert model_id == "state_v001"

    def test_version_padding(self):
        """Test version number padding."""
        assert generate_model_id(version=42) == "state_v042"
        assert generate_model_id(version=123) == "state_v123"


class TestListModels:
    """Tests for listing models."""

    def test_empty_list(self):
        """Test listing when no models exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            models = list_models("1Min", root=Path(tmpdir))
            assert models == []

    def test_list_models(self):
        """Test listing existing models."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "timeframe=1Min" / "model_id=state_v001").mkdir(parents=True)
            (root / "timeframe=1Min" / "model_id=state_v002").mkdir(parents=True)

            models = list_models("1Min", root=root)

            assert models == ["state_v001", "state_v002"]


class TestGetLatestModel:
    """Tests for getting latest model."""

    def test_no_models(self):
        """Test returns None when no models."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_latest_model("1Min", root=Path(tmpdir))
            assert result is None

    def test_returns_latest(self):
        """Test returns latest version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "timeframe=1Min" / "model_id=state_v001").mkdir(parents=True)
            (root / "timeframe=1Min" / "model_id=state_v003").mkdir(parents=True)
            (root / "timeframe=1Min" / "model_id=state_v002").mkdir(parents=True)

            paths = get_latest_model("1Min", root=root)

            assert paths is not None
            assert paths.model_id == "state_v003"


class TestGetModelPath:
    """Tests for get_model_path factory."""

    def test_basic_usage(self):
        """Test basic path retrieval."""
        paths = get_model_path("1Min", "state_v001")

        assert paths.timeframe == "1Min"
        assert paths.model_id == "state_v001"

    def test_custom_root(self):
        """Test custom root directory."""
        paths = get_model_path("1Hour", "state_v002", root=Path("/custom"))

        assert paths.root == Path("/custom")


class TestGetStatesPath:
    """Tests for get_states_path factory."""

    def test_basic_usage(self):
        """Test basic path retrieval."""
        paths = get_states_path("1Min", "state_v001")

        assert paths.timeframe == "1Min"
        assert paths.model_id == "state_v001"
