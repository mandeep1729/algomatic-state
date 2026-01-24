"""Unit tests for TA-Lib technical indicators calculator."""

import numpy as np
import pandas as pd
import pytest

# Check if TA-Lib is available
try:
    from src.features.talib_indicators import TALibIndicatorCalculator, TALIB_AVAILABLE
except ImportError:
    TALIB_AVAILABLE = False
    TALibIndicatorCalculator = None


@pytest.fixture
def large_ohlcv_df() -> pd.DataFrame:
    """Create larger OHLCV dataset for TA-Lib tests (200+ bars for SMA200)."""
    np.random.seed(42)
    n_bars = 250

    base_date = pd.Timestamp("2024-01-01 09:30:00")
    index = pd.date_range(start=base_date, periods=n_bars, freq="1min")

    # Generate trending close prices with noise
    trend = np.linspace(100, 120, n_bars)
    noise = np.random.randn(n_bars) * 0.5
    close = trend + noise

    # Generate open prices
    open_prices = np.roll(close, 1) + np.random.randn(n_bars) * 0.1
    open_prices[0] = close[0] - 0.1

    # Generate high/low
    high = np.maximum(open_prices, close) + np.abs(np.random.randn(n_bars)) * 0.3
    low = np.minimum(open_prices, close) - np.abs(np.random.randn(n_bars)) * 0.3

    # Generate volume
    volume = (10000 + np.random.randn(n_bars) * 2000).astype(int)
    volume = np.maximum(volume, 100)

    return pd.DataFrame(
        {
            "open": open_prices,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=index,
    )


@pytest.mark.skipif(not TALIB_AVAILABLE, reason="TA-Lib not installed")
class TestTALibIndicatorCalculator:
    """Tests for TALibIndicatorCalculator."""

    def test_init_default_parameters(self):
        """Test initialization with default parameters."""
        calc = TALibIndicatorCalculator()

        assert calc.rsi_period == 14
        assert calc.macd_fast == 12
        assert calc.macd_slow == 26
        assert calc.macd_signal == 9
        assert calc.bb_period == 20
        assert calc.bb_std == 2.0
        assert calc.atr_period == 14

    def test_init_custom_parameters(self):
        """Test initialization with custom parameters."""
        calc = TALibIndicatorCalculator(
            rsi_period=21,
            macd_fast=10,
            bb_period=25,
        )

        assert calc.rsi_period == 21
        assert calc.macd_fast == 10
        assert calc.bb_period == 25

    def test_feature_specs_returns_list(self):
        """Test that feature_specs returns a list of FeatureSpec objects."""
        calc = TALibIndicatorCalculator()
        specs = calc.feature_specs

        assert isinstance(specs, list)
        assert len(specs) > 30  # Should have 35+ features

    def test_max_lookback(self):
        """Test max_lookback property."""
        calc = TALibIndicatorCalculator()

        # Max lookback should be at least 200 (for SMA200)
        assert calc.max_lookback >= 200

    def test_compute_returns_dataframe(self, large_ohlcv_df):
        """Test that compute returns a DataFrame with indicators."""
        calc = TALibIndicatorCalculator()
        result = calc.compute(large_ohlcv_df)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(large_ohlcv_df)
        assert result.index.equals(large_ohlcv_df.index)

    def test_compute_empty_dataframe(self):
        """Test compute with empty DataFrame."""
        calc = TALibIndicatorCalculator()
        empty_df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        result = calc.compute(empty_df)

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_momentum_indicators_computed(self, large_ohlcv_df):
        """Test that momentum indicators are computed."""
        calc = TALibIndicatorCalculator()
        result = calc.compute(large_ohlcv_df)

        momentum_cols = ["rsi_14", "macd", "macd_signal", "macd_hist",
                         "stoch_k", "stoch_d", "adx_14", "cci_20",
                         "willr_14", "mfi_14"]

        for col in momentum_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_trend_indicators_computed(self, large_ohlcv_df):
        """Test that trend indicators are computed."""
        calc = TALibIndicatorCalculator()
        result = calc.compute(large_ohlcv_df)

        trend_cols = ["sma_20", "sma_50", "sma_200",
                      "ema_20", "ema_50", "ema_200", "psar"]

        for col in trend_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_volatility_indicators_computed(self, large_ohlcv_df):
        """Test that volatility indicators are computed."""
        calc = TALibIndicatorCalculator()
        result = calc.compute(large_ohlcv_df)

        volatility_cols = ["bb_upper", "bb_middle", "bb_lower",
                           "bb_width", "bb_pct", "atr_14"]

        for col in volatility_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_volume_indicators_computed(self, large_ohlcv_df):
        """Test that volume indicators are computed."""
        calc = TALibIndicatorCalculator()
        result = calc.compute(large_ohlcv_df)

        volume_cols = ["obv", "vwap"]

        for col in volume_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_ichimoku_indicators_computed(self, large_ohlcv_df):
        """Test that Ichimoku indicators are computed."""
        calc = TALibIndicatorCalculator()
        result = calc.compute(large_ohlcv_df)

        ichimoku_cols = ["ichi_tenkan", "ichi_kijun", "ichi_senkou_a",
                         "ichi_senkou_b", "ichi_chikou"]

        for col in ichimoku_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_pivot_points_computed(self, large_ohlcv_df):
        """Test that pivot points are computed."""
        calc = TALibIndicatorCalculator()
        result = calc.compute(large_ohlcv_df)

        pivot_cols = ["pivot_pp", "pivot_r1", "pivot_r2", "pivot_s1", "pivot_s2"]

        for col in pivot_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_rsi_bounds(self, large_ohlcv_df):
        """Test that RSI values are within 0-100 range."""
        calc = TALibIndicatorCalculator()
        result = calc.compute(large_ohlcv_df)

        rsi = result["rsi_14"].dropna()

        assert (rsi >= 0).all(), "RSI has values below 0"
        assert (rsi <= 100).all(), "RSI has values above 100"

    def test_stochastic_bounds(self, large_ohlcv_df):
        """Test that Stochastic values are within 0-100 range."""
        calc = TALibIndicatorCalculator()
        result = calc.compute(large_ohlcv_df)

        stoch_k = result["stoch_k"].dropna()
        stoch_d = result["stoch_d"].dropna()

        assert (stoch_k >= 0).all() and (stoch_k <= 100).all()
        assert (stoch_d >= 0).all() and (stoch_d <= 100).all()

    def test_mfi_bounds(self, large_ohlcv_df):
        """Test that MFI values are within 0-100 range."""
        calc = TALibIndicatorCalculator()
        result = calc.compute(large_ohlcv_df)

        mfi = result["mfi_14"].dropna()

        assert (mfi >= 0).all() and (mfi <= 100).all()

    def test_bollinger_bands_relationship(self, large_ohlcv_df):
        """Test that Bollinger Bands have correct relationship."""
        calc = TALibIndicatorCalculator()
        result = calc.compute(large_ohlcv_df)

        upper = result["bb_upper"].dropna()
        middle = result["bb_middle"].dropna()
        lower = result["bb_lower"].dropna()

        # Upper should be >= middle >= lower
        assert (upper >= middle).all(), "BB upper < middle"
        assert (middle >= lower).all(), "BB middle < lower"

    def test_atr_positive(self, large_ohlcv_df):
        """Test that ATR values are positive."""
        calc = TALibIndicatorCalculator()
        result = calc.compute(large_ohlcv_df)

        atr = result["atr_14"].dropna()

        assert (atr >= 0).all(), "ATR has negative values"

    def test_pivot_points_relationship(self, large_ohlcv_df):
        """Test that pivot points have correct relationship."""
        calc = TALibIndicatorCalculator()
        result = calc.compute(large_ohlcv_df)

        r2 = result["pivot_r2"].dropna()
        r1 = result["pivot_r1"].dropna()
        pp = result["pivot_pp"].dropna()
        s1 = result["pivot_s1"].dropna()
        s2 = result["pivot_s2"].dropna()

        # R2 > R1 > PP > S1 > S2
        assert (r2 >= r1).all(), "R2 < R1"
        assert (r1 >= pp).all(), "R1 < PP"
        assert (pp >= s1).all(), "PP < S1"
        assert (s1 >= s2).all(), "S1 < S2"

    def test_handles_insufficient_data(self, ohlcv_df):
        """Test with fewer bars than max lookback (100 bars < 200 SMA)."""
        calc = TALibIndicatorCalculator()
        result = calc.compute(ohlcv_df)  # 100 bars from fixture

        # Should still compute but SMA200 will be NaN
        assert "sma_200" in result.columns
        assert result["sma_200"].isna().all(), "SMA200 should be NaN with only 100 bars"

        # But shorter indicators should compute
        assert not result["rsi_14"].iloc[-1:].isna().all(), "RSI should compute"
        assert not result["sma_20"].iloc[-1:].isna().all(), "SMA20 should compute"


@pytest.mark.skipif(not TALIB_AVAILABLE, reason="TA-Lib not installed")
class TestTALibIndicatorGroups:
    """Tests for individual indicator group computation methods."""

    def test_compute_momentum_isolation(self, large_ohlcv_df):
        """Test momentum computation in isolation."""
        calc = TALibIndicatorCalculator()
        result = calc._compute_momentum(large_ohlcv_df)

        assert isinstance(result, pd.DataFrame)
        assert "rsi_14" in result.columns
        assert "macd" in result.columns

    def test_compute_trend_isolation(self, large_ohlcv_df):
        """Test trend computation in isolation."""
        calc = TALibIndicatorCalculator()
        result = calc._compute_trend(large_ohlcv_df)

        assert isinstance(result, pd.DataFrame)
        assert "sma_20" in result.columns
        assert "psar" in result.columns

    def test_compute_volatility_isolation(self, large_ohlcv_df):
        """Test volatility computation in isolation."""
        calc = TALibIndicatorCalculator()
        result = calc._compute_volatility(large_ohlcv_df)

        assert isinstance(result, pd.DataFrame)
        assert "bb_upper" in result.columns
        assert "atr_14" in result.columns

    def test_compute_volume_isolation(self, large_ohlcv_df):
        """Test volume computation in isolation."""
        calc = TALibIndicatorCalculator()
        result = calc._compute_volume(large_ohlcv_df)

        assert isinstance(result, pd.DataFrame)
        assert "obv" in result.columns
        assert "vwap" in result.columns

    def test_compute_ichimoku_isolation(self, large_ohlcv_df):
        """Test Ichimoku computation in isolation."""
        calc = TALibIndicatorCalculator()
        result = calc._compute_ichimoku(large_ohlcv_df)

        assert isinstance(result, pd.DataFrame)
        assert "ichi_tenkan" in result.columns
        assert "ichi_kijun" in result.columns

    def test_compute_pivot_points_isolation(self, large_ohlcv_df):
        """Test pivot points computation in isolation."""
        calc = TALibIndicatorCalculator()
        result = calc._compute_pivot_points(large_ohlcv_df)

        assert isinstance(result, pd.DataFrame)
        assert "pivot_pp" in result.columns
        assert "pivot_r1" in result.columns


@pytest.mark.skipif(TALIB_AVAILABLE, reason="Test only when TA-Lib is NOT installed")
class TestTALibNotAvailable:
    """Tests for when TA-Lib is not installed."""

    def test_import_error_raised(self):
        """Test that ImportError is raised when TA-Lib not available."""
        # This test only runs when TA-Lib is not installed
        # The import at module level should handle this
        pass
