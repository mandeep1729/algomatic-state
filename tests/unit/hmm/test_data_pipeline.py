"""Tests for HMM data pipeline."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from src.features.state.hmm.data_pipeline import (
    DataSplit,
    GapHandler,
    TimeSplitter,
    create_feature_vectors,
    validate_no_leakage,
)


class TestDataSplit:
    """Tests for DataSplit dataclass."""

    def test_valid_split(self):
        """Test creating a valid data split."""
        train = pd.DataFrame({"a": [1, 2, 3]}, index=pd.date_range("2024-01-01", periods=3))
        val = pd.DataFrame({"a": [4, 5]}, index=pd.date_range("2024-01-05", periods=2))

        split = DataSplit(
            train=train,
            val=val,
            test=None,
            train_start=train.index[0],
            train_end=train.index[-1],
            val_start=val.index[0],
            val_end=val.index[-1],
        )

        assert len(split.train) == 3
        assert len(split.val) == 2
        assert split.test is None

    def test_invalid_overlap(self):
        """Test that overlapping train/val raises error."""
        train = pd.DataFrame({"a": [1, 2, 3]}, index=pd.date_range("2024-01-01", periods=3))
        val = pd.DataFrame({"a": [4, 5]}, index=pd.date_range("2024-01-02", periods=2))

        with pytest.raises(ValueError, match="must be before"):
            DataSplit(
                train=train,
                val=val,
                test=None,
                train_start=train.index[0],
                train_end=train.index[-1],
                val_start=val.index[0],
                val_end=val.index[-1],
            )


class TestGapHandler:
    """Tests for GapHandler."""

    @pytest.fixture
    def gap_handler(self) -> GapHandler:
        """Create gap handler for 1-minute bars."""
        return GapHandler(timeframe="1Min", max_gap_bars=5)

    def test_detect_no_gaps(self, gap_handler: GapHandler):
        """Test detection when no gaps exist."""
        index = pd.date_range("2024-01-15 09:30", periods=10, freq="1min")
        df = pd.DataFrame({"a": range(10)}, index=index)

        gaps = gap_handler.detect_gaps(df)

        assert not gaps.any()

    def test_detect_gap(self, gap_handler: GapHandler):
        """Test detection of a gap."""
        index = pd.DatetimeIndex([
            datetime(2024, 1, 15, 9, 30),
            datetime(2024, 1, 15, 9, 31),
            datetime(2024, 1, 15, 9, 35),
            datetime(2024, 1, 15, 9, 36),
        ])
        df = pd.DataFrame({"a": [1, 2, 3, 4]}, index=index)

        gaps = gap_handler.detect_gaps(df)

        assert not gaps.iloc[0]
        assert not gaps.iloc[1]
        assert gaps.iloc[2]
        assert not gaps.iloc[3]

    def test_mark_gaps(self, gap_handler: GapHandler):
        """Test gap marking adds column."""
        index = pd.date_range("2024-01-15 09:30", periods=5, freq="1min")
        df = pd.DataFrame({"a": range(5)}, index=index)

        df_marked = gap_handler.mark_gaps(df)

        assert "has_gap" in df_marked.columns
        assert not df_marked["has_gap"].any()


class TestTimeSplitter:
    """Tests for TimeSplitter."""

    @pytest.fixture
    def sample_df(self) -> pd.DataFrame:
        """Create sample DataFrame for splitting."""
        index = pd.date_range("2024-01-01", periods=100, freq="1min")
        return pd.DataFrame({"a": range(100)}, index=index)

    def test_basic_split(self, sample_df: pd.DataFrame):
        """Test basic train/val/test split."""
        splitter = TimeSplitter(train_ratio=0.7, val_ratio=0.15, test_ratio=0.15)
        split = splitter.split(sample_df)

        assert len(split.train) == 70
        assert len(split.val) == 15
        assert split.test is not None
        assert len(split.test) == 15

    def test_gap_bars(self, sample_df: pd.DataFrame):
        """Test split with gap bars."""
        splitter = TimeSplitter(
            train_ratio=0.7,
            val_ratio=0.15,
            test_ratio=0.15,
            gap_bars=5,
        )
        split = splitter.split(sample_df)

        total_used = len(split.train) + len(split.val) + len(split.test)
        assert total_used < len(sample_df)

    def test_walk_forward_splits(self, sample_df: pd.DataFrame):
        """Test walk-forward validation splits."""
        splitter = TimeSplitter()
        splits = splitter.walk_forward_splits(
            sample_df,
            train_window=30,
            val_window=10,
            step=20,
        )

        assert len(splits) > 0
        for split in splits:
            assert len(split.train) == 30
            assert len(split.val) == 10

    def test_invalid_ratios(self):
        """Test that ratios not summing to 1 raise error."""
        with pytest.raises(ValueError, match="sum to 1"):
            TimeSplitter(train_ratio=0.5, val_ratio=0.3, test_ratio=0.3)

    def test_too_small_df(self):
        """Test that small DataFrame raises error."""
        df = pd.DataFrame({"a": [1, 2]}, index=pd.date_range("2024-01-01", periods=2))
        splitter = TimeSplitter()

        with pytest.raises(ValueError, match="too small"):
            splitter.split(df)


class TestValidateNoLeakage:
    """Tests for leakage validation."""

    def test_no_leakage(self):
        """Test validation passes when no leakage."""
        train = pd.DataFrame({"a": [1]}, index=pd.date_range("2024-01-01", periods=1))
        val = pd.DataFrame({"a": [2]}, index=pd.date_range("2024-01-05", periods=1))

        result = validate_no_leakage(train, val)
        assert result is True

    def test_leakage_detected(self):
        """Test validation fails when leakage exists."""
        train = pd.DataFrame({"a": [1]}, index=pd.date_range("2024-01-05", periods=1))
        val = pd.DataFrame({"a": [2]}, index=pd.date_range("2024-01-01", periods=1))

        with pytest.raises(ValueError, match="Leakage detected"):
            validate_no_leakage(train, val)


class TestCreateFeatureVectors:
    """Tests for feature vector creation."""

    def test_basic_creation(self):
        """Test creating feature vectors from DataFrame."""
        index = pd.date_range("2024-01-15 09:30", periods=3, freq="1min", tz=timezone.utc)
        df = pd.DataFrame(
            {"r5": [0.01, 0.02, -0.01], "vol": [0.1, 0.15, 0.12]},
            index=index,
        )

        vectors = create_feature_vectors(df, "AAPL", "1Min", ["r5", "vol"])

        assert len(vectors) == 3
        assert vectors[0].symbol == "AAPL"
        assert vectors[0].timeframe == "1Min"
        assert vectors[0].features["r5"] == 0.01
        assert vectors[1].features["vol"] == 0.15

    def test_with_gap_column(self):
        """Test creation with has_gap column."""
        index = pd.date_range("2024-01-15 09:30", periods=3, freq="1min", tz=timezone.utc)
        df = pd.DataFrame(
            {
                "r5": [0.01, 0.02, -0.01],
                "has_gap": [False, True, False],
            },
            index=index,
        )

        vectors = create_feature_vectors(df, "AAPL", "1Min", ["r5"])

        assert not vectors[0].has_gap
        assert vectors[1].has_gap
        assert not vectors[2].has_gap
