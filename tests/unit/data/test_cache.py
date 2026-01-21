"""Unit tests for data cache."""

from datetime import datetime

import pandas as pd
import pytest

from src.data.cache import DataCache


@pytest.fixture
def temp_cache(tmp_path):
    """Create a temporary cache directory."""
    return DataCache(cache_dir=tmp_path / "cache")


@pytest.fixture
def sample_df():
    """Create a sample OHLCV DataFrame."""
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


class TestDataCache:
    """Test suite for DataCache."""

    def test_cache_miss_returns_none(self, temp_cache):
        """Test that cache miss returns None."""
        result = temp_cache.get(
            "AAPL",
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
        )
        assert result is None

    def test_put_and_get(self, temp_cache, sample_df):
        """Test storing and retrieving data from cache."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)

        # Store data
        cache_path = temp_cache.put("AAPL", start, end, sample_df)
        assert cache_path.exists()

        # Retrieve data
        result = temp_cache.get("AAPL", start, end)
        assert result is not None
        assert len(result) == len(sample_df)
        pd.testing.assert_frame_equal(result, sample_df)

    def test_cache_key_uniqueness(self, temp_cache, sample_df):
        """Test that different parameters produce different cache keys."""
        start1 = datetime(2024, 1, 1)
        end1 = datetime(2024, 1, 2)
        start2 = datetime(2024, 1, 2)
        end2 = datetime(2024, 1, 3)

        temp_cache.put("AAPL", start1, end1, sample_df)
        temp_cache.put("AAPL", start2, end2, sample_df)

        # Different date ranges should not overwrite
        result1 = temp_cache.get("AAPL", start1, end1)
        result2 = temp_cache.get("AAPL", start2, end2)

        assert result1 is not None
        assert result2 is not None

    def test_different_symbols_separate(self, temp_cache, sample_df):
        """Test that different symbols are cached separately."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)

        temp_cache.put("AAPL", start, end, sample_df)
        temp_cache.put("GOOG", start, end, sample_df)

        # Different symbols should be independent
        aapl = temp_cache.get("AAPL", start, end)
        goog = temp_cache.get("GOOG", start, end)

        assert aapl is not None
        assert goog is not None

    def test_clear_specific_symbol(self, temp_cache, sample_df):
        """Test clearing cache for a specific symbol."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)

        temp_cache.put("AAPL", start, end, sample_df)
        temp_cache.put("GOOG", start, end, sample_df)

        # Clear only AAPL
        count = temp_cache.clear("AAPL")
        assert count == 1

        # AAPL should be gone, GOOG should remain
        assert temp_cache.get("AAPL", start, end) is None
        assert temp_cache.get("GOOG", start, end) is not None

    def test_clear_all(self, temp_cache, sample_df):
        """Test clearing entire cache."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)

        temp_cache.put("AAPL", start, end, sample_df)
        temp_cache.put("GOOG", start, end, sample_df)

        # Clear all
        count = temp_cache.clear()
        assert count == 2

        assert temp_cache.get("AAPL", start, end) is None
        assert temp_cache.get("GOOG", start, end) is None

    def test_list_cached(self, temp_cache, sample_df):
        """Test listing cached entries."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)

        temp_cache.put("AAPL", start, end, sample_df)
        temp_cache.put("GOOG", start, end, sample_df)

        entries = temp_cache.list_cached()
        assert len(entries) == 2

        symbols = {e["symbol"] for e in entries}
        assert "AAPL" in symbols
        assert "GOOG" in symbols

    def test_list_cached_by_symbol(self, temp_cache, sample_df):
        """Test listing cached entries for specific symbol."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)

        temp_cache.put("AAPL", start, end, sample_df)
        temp_cache.put("GOOG", start, end, sample_df)

        entries = temp_cache.list_cached("AAPL")
        assert len(entries) == 1
        assert entries[0]["symbol"] == "AAPL"

    def test_symbol_case_insensitive(self, temp_cache, sample_df):
        """Test that symbols are case-insensitive."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)

        temp_cache.put("aapl", start, end, sample_df)
        result = temp_cache.get("AAPL", start, end)

        # Should find it regardless of case
        assert result is not None
