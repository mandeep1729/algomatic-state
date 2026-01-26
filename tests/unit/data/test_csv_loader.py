"""Unit tests for CSV loader."""

from datetime import datetime
from pathlib import Path
from textwrap import dedent

import pandas as pd
import pandera.pandas.errors as pandera_errors
import pytest

from src.data.loaders.csv_loader import CSVLoader


@pytest.fixture
def temp_csv(tmp_path):
    """Create a temporary CSV file with given content."""

    def _create(content: str, filename: str = "test.csv") -> Path:
        path = tmp_path / filename
        path.write_text(dedent(content).strip())
        return path

    return _create


class TestCSVLoader:
    """Test suite for CSVLoader."""

    def test_load_basic_csv(self, temp_csv):
        """Test loading a basic CSV with standard column names."""
        csv_content = """
        Date,Open,High,Low,Close,Volume
        2024-01-01 09:30,100.0,101.0,99.0,100.5,1000
        2024-01-01 09:31,100.5,102.0,100.0,101.5,1500
        2024-01-01 09:32,101.5,101.5,100.5,101.0,1200
        """
        path = temp_csv(csv_content)
        loader = CSVLoader()

        df = loader.load(path)

        assert len(df) == 3
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert isinstance(df.index, pd.DatetimeIndex)
        assert df.index.name == "timestamp"

    def test_load_dd_mm_yyyy_format(self, temp_csv):
        """Test loading CSV with DD/MM/YYYY HH:MM date format (oil_all.csv style)."""
        csv_content = """
        Date,Open,High,Low,Close,Volume
        07/06/2016 22:59,50.42,50.44,50.40,50.43,105
        07/06/2016 22:58,50.44,50.44,50.42,50.42,84
        """
        path = temp_csv(csv_content)
        loader = CSVLoader()

        df = loader.load(path)

        assert len(df) == 2
        # DD/MM/YYYY: 07/06/2016 is June 7, 2016
        assert df.index[0].month == 6
        assert df.index[0].day == 7
        assert df.index[0].year == 2016

    def test_load_iso_format(self, temp_csv):
        """Test loading CSV with ISO 8601 date format."""
        csv_content = """
        timestamp,open,high,low,close,volume
        2024-01-01T09:30:00,100.0,101.0,99.0,100.5,1000
        2024-01-01T09:31:00,100.5,102.0,100.0,101.5,1500
        """
        path = temp_csv(csv_content)
        loader = CSVLoader()

        df = loader.load(path)

        assert len(df) == 2
        assert df.index[0] == pd.Timestamp("2024-01-01 09:30:00")

    def test_column_name_normalization(self, temp_csv):
        """Test that various column names are normalized."""
        csv_content = """
        DateTime,O,H,L,C,Vol
        2024-01-01 09:30,100.0,101.0,99.0,100.5,1000
        """
        path = temp_csv(csv_content)
        loader = CSVLoader()

        df = loader.load(path)

        assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    def test_date_filtering_start(self, temp_csv):
        """Test filtering by start date."""
        csv_content = """
        Date,Open,High,Low,Close,Volume
        2024-01-01 09:30,100.0,101.0,99.0,100.5,1000
        2024-01-02 09:30,100.5,102.0,100.0,101.5,1500
        2024-01-03 09:30,101.5,101.5,100.5,101.0,1200
        """
        path = temp_csv(csv_content)
        loader = CSVLoader()

        df = loader.load(path, start=datetime(2024, 1, 2))

        assert len(df) == 2
        assert df.index[0] == pd.Timestamp("2024-01-02 09:30:00")

    def test_date_filtering_end(self, temp_csv):
        """Test filtering by end date."""
        csv_content = """
        Date,Open,High,Low,Close,Volume
        2024-01-01 09:30,100.0,101.0,99.0,100.5,1000
        2024-01-02 09:30,100.5,102.0,100.0,101.5,1500
        2024-01-03 09:30,101.5,101.5,100.5,101.0,1200
        """
        path = temp_csv(csv_content)
        loader = CSVLoader()

        # Use end of day to include all Jan 2 data
        df = loader.load(path, end=datetime(2024, 1, 2, 23, 59, 59))

        assert len(df) == 2
        assert df.index[-1] == pd.Timestamp("2024-01-02 09:30:00")

    def test_date_filtering_range(self, temp_csv):
        """Test filtering by both start and end date."""
        csv_content = """
        Date,Open,High,Low,Close,Volume
        2024-01-01 09:30,100.0,101.0,99.0,100.5,1000
        2024-01-02 09:30,100.5,102.0,100.0,101.5,1500
        2024-01-03 09:30,101.5,101.5,100.5,101.0,1200
        """
        path = temp_csv(csv_content)
        loader = CSVLoader()

        df = loader.load(
            path,
            start=datetime(2024, 1, 2),
            end=datetime(2024, 1, 2, 23, 59),
        )

        assert len(df) == 1
        assert df.index[0] == pd.Timestamp("2024-01-02 09:30:00")

    def test_missing_value_handling(self, temp_csv):
        """Test that missing values are filled."""
        csv_content = """
        Date,Open,High,Low,Close,Volume
        2024-01-01 09:30,100.0,101.0,99.0,100.5,1000
        2024-01-01 09:31,,102.0,100.0,101.5,
        2024-01-01 09:32,101.5,101.5,100.5,101.0,1200
        """
        path = temp_csv(csv_content)
        loader = CSVLoader(fill_missing=True)

        df = loader.load(path)

        # Open should be forward-filled from previous row
        assert df.loc[df.index[1], "open"] == 100.0
        # Volume should be 0
        assert df.loc[df.index[1], "volume"] == 0

    def test_data_sorted_by_timestamp(self, temp_csv):
        """Test that data is sorted by timestamp."""
        csv_content = """
        Date,Open,High,Low,Close,Volume
        2024-01-01 09:32,101.5,101.5,100.5,101.0,1200
        2024-01-01 09:30,100.0,101.0,99.0,100.5,1000
        2024-01-01 09:31,100.5,102.0,100.0,101.5,1500
        """
        path = temp_csv(csv_content)
        loader = CSVLoader()

        df = loader.load(path)

        assert df.index[0] == pd.Timestamp("2024-01-01 09:30:00")
        assert df.index[1] == pd.Timestamp("2024-01-01 09:31:00")
        assert df.index[2] == pd.Timestamp("2024-01-01 09:32:00")

    def test_file_not_found(self):
        """Test that FileNotFoundError is raised for missing files."""
        loader = CSVLoader()

        with pytest.raises(FileNotFoundError):
            loader.load("/nonexistent/path.csv")

    def test_missing_timestamp_column(self, temp_csv):
        """Test error when timestamp column is missing."""
        csv_content = """
        Open,High,Low,Close,Volume
        100.0,101.0,99.0,100.5,1000
        """
        path = temp_csv(csv_content)
        loader = CSVLoader()

        with pytest.raises(ValueError, match="timestamp column"):
            loader.load(path)

    def test_missing_required_column(self, temp_csv):
        """Test error when required OHLCV column is missing."""
        csv_content = """
        Date,Open,High,Low,Volume
        2024-01-01 09:30,100.0,101.0,99.0,1000
        """
        path = temp_csv(csv_content)
        loader = CSVLoader()

        with pytest.raises(ValueError, match="close"):
            loader.load(path)

    def test_validation_high_low_consistency(self, temp_csv):
        """Test validation fails when high < low."""
        csv_content = """
        Date,Open,High,Low,Close,Volume
        2024-01-01 09:30,100.0,99.0,101.0,100.5,1000
        """
        path = temp_csv(csv_content)
        loader = CSVLoader(validate=True)

        with pytest.raises(pandera_errors.SchemaError):
            loader.load(path)

    def test_validation_negative_price(self, temp_csv):
        """Test validation fails for negative prices."""
        csv_content = """
        Date,Open,High,Low,Close,Volume
        2024-01-01 09:30,-100.0,101.0,99.0,100.5,1000
        """
        path = temp_csv(csv_content)
        loader = CSVLoader(validate=True)

        with pytest.raises(pandera_errors.SchemaError):
            loader.load(path)

    def test_skip_validation(self, temp_csv):
        """Test that validation can be skipped."""
        csv_content = """
        Date,Open,High,Low,Close,Volume
        2024-01-01 09:30,100.0,99.0,101.0,100.5,1000
        """
        path = temp_csv(csv_content)
        loader = CSVLoader(validate=False)

        # Should not raise even with invalid data
        df = loader.load(path)
        assert len(df) == 1

    def test_load_multiple_files(self, temp_csv):
        """Test loading multiple CSV files."""
        content1 = """
        Date,Open,High,Low,Close,Volume
        2024-01-01 09:30,100.0,101.0,99.0,100.5,1000
        """
        content2 = """
        Date,Open,High,Low,Close,Volume
        2024-01-01 09:30,200.0,201.0,199.0,200.5,2000
        """
        path1 = temp_csv(content1, "stock1.csv")
        path2 = temp_csv(content2, "stock2.csv")

        loader = CSVLoader()
        result = loader.load_multiple([path1, path2])

        assert "stock1" in result
        assert "stock2" in result
        assert result["stock1"].iloc[0]["close"] == 100.5
        assert result["stock2"].iloc[0]["close"] == 200.5

    def test_extra_columns_preserved_during_load(self, temp_csv):
        """Test that extra columns don't cause errors (but are dropped)."""
        csv_content = """
        Date,Open,High,Low,Close,Volume,Ticks,ExtraCol
        2024-01-01 09:30,100.0,101.0,99.0,100.5,1000,50,abc
        """
        path = temp_csv(csv_content)
        loader = CSVLoader()

        df = loader.load(path)

        # Extra columns should be dropped, only OHLCV remain
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]


class TestCSVLoaderWithRealData:
    """Tests using real data file if available."""

    @pytest.fixture
    def oil_csv_path(self):
        """Path to the oil_all.csv file."""
        path = Path(__file__).parent.parent.parent.parent / "data" / "oil_all.csv"
        if not path.exists():
            pytest.skip("oil_all.csv not found")
        return path

    def test_load_oil_data(self, oil_csv_path):
        """Test loading the actual oil_all.csv file."""
        loader = CSVLoader()

        df = loader.load(oil_csv_path)

        assert len(df) > 0
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert isinstance(df.index, pd.DatetimeIndex)
        # Check no NaN values
        assert not df.isnull().any().any()

    def test_load_oil_data_with_date_range(self, oil_csv_path):
        """Test loading oil data with date filtering."""
        loader = CSVLoader()

        # The data uses DD/MM/YYYY, so "07/06/2016" is June 7, 2016
        df = loader.load(
            oil_csv_path,
            start=datetime(2016, 6, 7),
            end=datetime(2016, 6, 7, 23, 59, 59),
        )

        assert len(df) > 0
        assert df.index.min() >= pd.Timestamp("2016-06-07")
        assert df.index.max() <= pd.Timestamp("2016-06-07 23:59:59")
