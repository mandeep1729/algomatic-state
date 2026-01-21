"""Unit tests for multi-asset loader."""

from datetime import datetime
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.data.loaders.csv_loader import CSVLoader
from src.data.loaders.multi_asset import (
    MultiAssetLoader,
    align_timestamps,
    load_and_combine,
)


@pytest.fixture
def sample_df_aapl():
    """Sample OHLCV DataFrame for AAPL."""
    dates = pd.date_range("2024-01-01 09:30", periods=5, freq="1min")
    return pd.DataFrame(
        {
            "open": [100.0, 100.5, 101.0, 100.5, 101.5],
            "high": [101.0, 102.0, 101.5, 101.0, 102.0],
            "low": [99.5, 100.0, 100.5, 100.0, 101.0],
            "close": [100.5, 101.5, 101.0, 100.5, 101.5],
            "volume": [1000, 1500, 1200, 800, 2000],
        },
        index=dates,
    )


@pytest.fixture
def sample_df_goog():
    """Sample OHLCV DataFrame for GOOG with different timestamps."""
    # Missing the 09:32 bar (third bar)
    dates = pd.DatetimeIndex([
        "2024-01-01 09:30",
        "2024-01-01 09:31",
        "2024-01-01 09:33",
        "2024-01-01 09:34",
    ])
    return pd.DataFrame(
        {
            "open": [150.0, 150.5, 151.5, 152.0],
            "high": [151.0, 152.0, 152.0, 153.0],
            "low": [149.5, 150.0, 151.0, 151.5],
            "close": [150.5, 151.5, 151.5, 152.5],
            "volume": [2000, 2500, 1800, 2200],
        },
        index=dates,
    )


class TestAlignTimestamps:
    """Test suite for align_timestamps function."""

    def test_empty_data(self):
        """Test alignment with empty data."""
        result = align_timestamps({})
        assert result == {}

    def test_single_dataframe(self, sample_df_aapl):
        """Test alignment with single DataFrame (no-op)."""
        data = {"AAPL": sample_df_aapl}
        result = align_timestamps(data)
        assert len(result) == 1
        pd.testing.assert_frame_equal(result["AAPL"], sample_df_aapl)

    def test_inner_alignment(self, sample_df_aapl, sample_df_goog):
        """Test inner alignment keeps only common timestamps."""
        data = {"AAPL": sample_df_aapl, "GOOG": sample_df_goog}
        result = align_timestamps(data, method="inner")

        # Only timestamps 09:30, 09:31, 09:33, 09:34 are in both
        # But AAPL has 09:30, 09:31, 09:32, 09:33, 09:34
        # GOOG has 09:30, 09:31, 09:33, 09:34 (missing 09:32)
        # Inner should have 09:30, 09:31, 09:33, 09:34
        expected_times = pd.DatetimeIndex([
            "2024-01-01 09:30",
            "2024-01-01 09:31",
            "2024-01-01 09:33",
            "2024-01-01 09:34",
        ])

        assert len(result["AAPL"]) == 4
        assert len(result["GOOG"]) == 4
        assert result["AAPL"].index.tolist() == expected_times.tolist()
        assert result["GOOG"].index.tolist() == expected_times.tolist()

    def test_outer_alignment(self, sample_df_aapl, sample_df_goog):
        """Test outer alignment keeps all timestamps."""
        data = {"AAPL": sample_df_aapl, "GOOG": sample_df_goog}
        result = align_timestamps(data, method="outer", fill_method=None)

        # Union of all timestamps
        # AAPL: 09:30, 09:31, 09:32, 09:33, 09:34
        # GOOG: 09:30, 09:31, 09:33, 09:34
        # Union: 09:30, 09:31, 09:32, 09:33, 09:34
        expected_len = 5

        assert len(result["AAPL"]) == expected_len
        assert len(result["GOOG"]) == expected_len

        # GOOG should have NaN for 09:32 (no fill)
        assert pd.isna(result["GOOG"].loc["2024-01-01 09:32", "open"])

    def test_outer_alignment_with_ffill(self, sample_df_aapl, sample_df_goog):
        """Test outer alignment with forward fill."""
        data = {"AAPL": sample_df_aapl, "GOOG": sample_df_goog}
        result = align_timestamps(data, method="outer", fill_method="ffill")

        # GOOG's 09:32 should be forward-filled from 09:31
        assert result["GOOG"].loc["2024-01-01 09:32", "close"] == 151.5

    def test_preserves_empty_dataframes(self, sample_df_aapl):
        """Test that empty DataFrames are preserved."""
        data = {"AAPL": sample_df_aapl, "EMPTY": pd.DataFrame()}
        result = align_timestamps(data, method="inner")

        assert not result["AAPL"].empty
        assert result["EMPTY"].empty


class TestMultiAssetLoader:
    """Test suite for MultiAssetLoader."""

    @pytest.fixture
    def mock_loader(self, sample_df_aapl, sample_df_goog):
        """Create a mock loader."""
        loader = MagicMock()

        def load_mock(source, start=None, end=None):
            if str(source).upper() == "AAPL":
                return sample_df_aapl
            elif str(source).upper() == "GOOG":
                return sample_df_goog
            raise ValueError(f"Unknown symbol: {source}")

        loader.load.side_effect = load_mock
        return loader

    def test_load_multiple_sequential(self, mock_loader, sample_df_aapl, sample_df_goog):
        """Test sequential loading of multiple assets."""
        multi_loader = MultiAssetLoader(mock_loader, align=False)

        result = multi_loader.load(
            ["AAPL", "GOOG"],
            start=datetime(2024, 1, 1),
            parallel=False,
        )

        assert "AAPL" in result
        assert "GOOG" in result
        assert len(result["AAPL"]) == 5
        assert len(result["GOOG"]) == 4

    def test_load_multiple_parallel(self, mock_loader):
        """Test parallel loading of multiple assets."""
        multi_loader = MultiAssetLoader(mock_loader, max_workers=2, align=False)

        result = multi_loader.load(
            ["AAPL", "GOOG"],
            start=datetime(2024, 1, 1),
            parallel=True,
        )

        assert "AAPL" in result
        assert "GOOG" in result
        # Both should be called
        assert mock_loader.load.call_count == 2

    def test_load_with_alignment(self, mock_loader):
        """Test loading with timestamp alignment."""
        multi_loader = MultiAssetLoader(
            mock_loader,
            align=True,
            align_method="inner",
        )

        result = multi_loader.load(
            ["AAPL", "GOOG"],
            start=datetime(2024, 1, 1),
        )

        # Both should have same timestamps after inner alignment
        assert len(result["AAPL"]) == len(result["GOOG"])
        assert result["AAPL"].index.tolist() == result["GOOG"].index.tolist()

    def test_error_handling_warn(self, mock_loader):
        """Test error handling with warn strategy."""
        mock_loader.load.side_effect = Exception("API Error")
        multi_loader = MultiAssetLoader(mock_loader, align=False)

        result = multi_loader.load(["AAPL"], on_error="warn")

        assert "AAPL" in result
        assert result["AAPL"].empty

    def test_error_handling_raise(self, mock_loader):
        """Test error handling with raise strategy."""
        mock_loader.load.side_effect = Exception("API Error")
        multi_loader = MultiAssetLoader(mock_loader, align=False)

        with pytest.raises(RuntimeError, match="Failed to load"):
            multi_loader.load(["AAPL"], on_error="raise")

    def test_error_handling_skip(self, mock_loader, sample_df_aapl):
        """Test error handling with skip strategy."""

        def load_mock(source, start=None, end=None):
            if str(source).upper() == "AAPL":
                return sample_df_aapl
            raise Exception("API Error")

        mock_loader.load.side_effect = load_mock
        multi_loader = MultiAssetLoader(mock_loader, align=False)

        result = multi_loader.load(["AAPL", "GOOG"], on_error="skip")

        assert len(result["AAPL"]) == 5
        assert result["GOOG"].empty


class TestLoadAndCombine:
    """Test suite for load_and_combine function."""

    def test_panel_method(self, sample_df_aapl, sample_df_goog):
        """Test panel combine method returns dict as-is."""
        data = {"AAPL": sample_df_aapl, "GOOG": sample_df_goog}
        result = load_and_combine(data, combine_method="panel")

        assert result == data

    def test_columns_method(self, sample_df_aapl, sample_df_goog):
        """Test columns combine method creates multi-column DataFrame."""
        data = {"AAPL": sample_df_aapl, "GOOG": sample_df_goog}
        result = load_and_combine(data, combine_method="columns")

        # Should be a single DataFrame
        assert isinstance(result, pd.DataFrame)

        # Should have combined columns
        expected_cols = ["AAPL_open", "AAPL_high", "AAPL_low", "AAPL_close", "AAPL_volume",
                         "GOOG_open", "GOOG_high", "GOOG_low", "GOOG_close", "GOOG_volume"]
        for col in expected_cols:
            assert col in result.columns

    def test_invalid_method_raises(self, sample_df_aapl):
        """Test that invalid method raises ValueError."""
        data = {"AAPL": sample_df_aapl}

        with pytest.raises(ValueError, match="Unknown combine_method"):
            load_and_combine(data, combine_method="invalid")


class TestMultiAssetLoaderWithCSV:
    """Integration tests using real CSVLoader."""

    @pytest.fixture
    def temp_csv(self, tmp_path):
        """Create temporary CSV files."""

        def _create(content: str, filename: str) -> Path:
            path = tmp_path / filename
            path.write_text(dedent(content).strip())
            return path

        return _create

    def test_load_multiple_csv_files(self, temp_csv):
        """Test loading multiple CSV files with alignment."""
        content1 = """
        Date,Open,High,Low,Close,Volume
        2024-01-01 09:30,100.0,101.0,99.0,100.5,1000
        2024-01-01 09:31,100.5,102.0,100.0,101.5,1500
        2024-01-01 09:32,101.5,102.0,101.0,101.5,1200
        """
        content2 = """
        Date,Open,High,Low,Close,Volume
        2024-01-01 09:30,200.0,201.0,199.0,200.5,2000
        2024-01-01 09:32,201.5,202.0,201.0,201.5,2200
        """
        path1 = temp_csv(content1, "stock1.csv")
        path2 = temp_csv(content2, "stock2.csv")

        loader = CSVLoader(validate=False)
        multi_loader = MultiAssetLoader(
            loader,
            align=True,
            align_method="inner",
        )

        result = multi_loader.load([path1, path2])

        # Inner alignment: only 09:30 and 09:32 are common
        assert len(result["stock1"]) == 2
        assert len(result["stock2"]) == 2
        assert result["stock1"].index.tolist() == result["stock2"].index.tolist()
