"""Unit tests for Alpaca loader."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data.loaders.alpaca_loader import AlpacaLoader, RateLimiter


@pytest.fixture
def sample_bars_df():
    """Create sample DataFrame mimicking Alpaca response."""
    dates = pd.date_range("2024-01-02 09:30", periods=5, freq="1min", tz="UTC")
    return pd.DataFrame(
        {
            "open": [100.0, 100.5, 101.0, 100.5, 101.5],
            "high": [101.0, 102.0, 101.5, 101.0, 102.0],
            "low": [99.5, 100.0, 100.5, 100.0, 101.0],
            "close": [100.5, 101.5, 101.0, 100.5, 101.5],
            "volume": [1000, 1500, 1200, 800, 2000],
            "trade_count": [50, 75, 60, 40, 100],
            "vwap": [100.25, 101.0, 101.0, 100.25, 101.5],
        },
        index=dates,
    )


@pytest.fixture
def mock_alpaca_client(sample_bars_df):
    """Create a mocked Alpaca client."""
    with patch("src.marketdata.alpaca_provider.StockHistoricalDataClient") as mock:
        client_instance = MagicMock()

        def _make_response(request):
            """Return a response that matches any requested symbol."""
            symbol = request.symbol_or_symbols
            resp = MagicMock()
            resp.df = sample_bars_df
            resp.data = {symbol: [MagicMock()]}
            return resp

        client_instance.get_stock_bars.side_effect = _make_response
        mock.return_value = client_instance

        yield mock


class TestRateLimiter:
    """Test suite for RateLimiter."""

    def test_first_call_no_wait(self):
        """Test that first call doesn't wait."""
        limiter = RateLimiter(calls_per_minute=6000)  # Fast rate for testing
        import time

        start = time.time()
        limiter.wait()
        elapsed = time.time() - start

        # First call should be nearly instant
        assert elapsed < 0.1

    def test_respects_rate_limit(self):
        """Test that rate limiter enforces minimum interval."""
        limiter = RateLimiter(calls_per_minute=600)  # 10 calls per second = 0.1s interval
        import time

        limiter.wait()
        start = time.time()
        limiter.wait()
        elapsed = time.time() - start

        # Should wait approximately 0.1 second
        assert elapsed >= 0.09


class TestAlpacaLoader:
    """Test suite for AlpacaLoader."""

    def test_requires_credentials(self):
        """Test that loader requires API credentials."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="credentials required"):
                AlpacaLoader()

    def test_accepts_direct_credentials(self, mock_alpaca_client, tmp_path):
        """Test that loader accepts direct credentials."""
        loader = AlpacaLoader(
            api_key="test_key",
            secret_key="test_secret",
            cache_dir=tmp_path / "cache",
            use_cache=False,
            rate_limit=60000,
        )
        assert loader.api_key == "test_key"
        assert loader.secret_key == "test_secret"

    def test_accepts_env_credentials(self, mock_alpaca_client, tmp_path):
        """Test that loader reads from environment variables."""
        with patch.dict(
            "os.environ",
            {"ALPACA_API_KEY": "env_key", "ALPACA_SECRET_KEY": "env_secret"},
        ):
            loader = AlpacaLoader(
                cache_dir=tmp_path / "cache",
                use_cache=False,
                rate_limit=60000,
            )
            assert loader.api_key == "env_key"
            assert loader.secret_key == "env_secret"

    def test_requires_start_date(self, mock_alpaca_client, tmp_path):
        """Test that load requires a start date."""
        loader = AlpacaLoader(
            api_key="test_key",
            secret_key="test_secret",
            cache_dir=tmp_path / "cache",
            use_cache=False,
            rate_limit=60000,
        )

        with pytest.raises(ValueError, match="Start date is required"):
            loader.load("AAPL")

    def test_load_returns_ohlcv_dataframe(
        self, mock_alpaca_client, sample_bars_df, tmp_path
    ):
        """Test that load returns properly formatted DataFrame."""
        loader = AlpacaLoader(
            api_key="test_key",
            secret_key="test_secret",
            cache_dir=tmp_path / "cache",
            use_cache=False,
            validate=False,
            rate_limit=60000,
        )

        df = loader.load("AAPL", start=datetime(2024, 1, 2), end=datetime(2024, 1, 3))

        assert len(df) == 5
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert df.index.name == "timestamp"

    def test_load_uses_cache(self, mock_alpaca_client, sample_bars_df, tmp_path):
        """Test that loader uses cache on second call."""
        loader = AlpacaLoader(
            api_key="test_key",
            secret_key="test_secret",
            cache_dir=tmp_path / "cache",
            use_cache=True,
            validate=False,
            rate_limit=60000,
        )

        start = datetime(2024, 1, 2)
        end = datetime(2024, 1, 3)

        # First call - should hit API
        df1 = loader.load("AAPL", start=start, end=end)

        # Reset mock call count
        loader._provider.client.get_stock_bars.reset_mock()

        # Second call - should use cache
        df2 = loader.load("AAPL", start=start, end=end)

        # API should not have been called again
        loader._provider.client.get_stock_bars.assert_not_called()

        # Results should be equal
        pd.testing.assert_frame_equal(df1, df2)

    def test_load_multiple_symbols(self, mock_alpaca_client, tmp_path):
        """Test loading multiple symbols."""
        loader = AlpacaLoader(
            api_key="test_key",
            secret_key="test_secret",
            cache_dir=tmp_path / "cache",
            use_cache=False,
            validate=False,
            rate_limit=60000,
        )

        result = loader.load_multiple(
            ["AAPL", "GOOG"],
            start=datetime(2024, 1, 2),
            end=datetime(2024, 1, 3),
        )

        assert "AAPL" in result
        assert "GOOG" in result
        assert len(result["AAPL"]) == 5
        assert len(result["GOOG"]) == 5

    def test_symbol_uppercased(self, mock_alpaca_client, tmp_path):
        """Test that symbols are uppercased."""
        loader = AlpacaLoader(
            api_key="test_key",
            secret_key="test_secret",
            cache_dir=tmp_path / "cache",
            use_cache=False,
            validate=False,
            rate_limit=60000,
        )

        df = loader.load("aapl", start=datetime(2024, 1, 2), end=datetime(2024, 1, 3))

        # Should work regardless of case
        assert len(df) == 5

    def test_retry_on_failure(self, mock_alpaca_client, tmp_path):
        """Test that loader retries on API failure."""
        loader = AlpacaLoader(
            api_key="test_key",
            secret_key="test_secret",
            cache_dir=tmp_path / "cache",
            use_cache=False,
            validate=False,
            max_retries=3,
            rate_limit=60000,
        )

        # Make first two calls fail, third succeed
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("API Error")
            mock_response = MagicMock()
            mock_response.df = pd.DataFrame(
                {
                    "open": [100.0],
                    "high": [101.0],
                    "low": [99.0],
                    "close": [100.5],
                    "volume": [1000],
                },
                index=pd.date_range("2024-01-02 09:30", periods=1, freq="1min", tz="UTC"),
            )
            mock_response.data = {"AAPL": [MagicMock()]}
            return mock_response

        loader._provider.client.get_stock_bars.side_effect = side_effect

        # Should eventually succeed
        df = loader.load("AAPL", start=datetime(2024, 1, 2), end=datetime(2024, 1, 3))
        assert len(df) == 1

    def test_max_retries_exceeded(self, mock_alpaca_client, tmp_path):
        """Test that loader raises after max retries."""
        loader = AlpacaLoader(
            api_key="test_key",
            secret_key="test_secret",
            cache_dir=tmp_path / "cache",
            use_cache=False,
            validate=False,
            max_retries=2,
            rate_limit=60000,
        )

        # Make all calls fail
        loader._provider.client.get_stock_bars.side_effect = Exception("API Error")

        with pytest.raises(RuntimeError, match="Failed after"):
            loader.load("AAPL", start=datetime(2024, 1, 2), end=datetime(2024, 1, 3))

    def test_empty_response_handled(self, mock_alpaca_client, tmp_path):
        """Test handling of empty API response."""
        loader = AlpacaLoader(
            api_key="test_key",
            secret_key="test_secret",
            cache_dir=tmp_path / "cache",
            use_cache=False,
            validate=False,
            rate_limit=60000,
        )

        # Mock empty response — clear side_effect so return_value is used
        mock_response = MagicMock()
        mock_response.data = {}
        loader._provider.client.get_stock_bars.side_effect = None
        loader._provider.client.get_stock_bars.return_value = mock_response

        df = loader.load("AAPL", start=datetime(2024, 1, 2), end=datetime(2024, 1, 3))

        assert df.empty
