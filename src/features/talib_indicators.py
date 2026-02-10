"""TA-Lib based technical indicators calculator.

Computes comprehensive technical indicators using TA-Lib library.
Includes momentum, trend, volatility, volume, and support/resistance indicators.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from .base import BaseFeatureCalculator, FeatureSpec

logger = logging.getLogger(__name__)

# Check for TA-Lib availability
try:
    import talib

    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    logger.warning(
        "TA-Lib not installed. TALibIndicatorCalculator will not be available. "
        "Install with: pip install TA-Lib (requires system TA-Lib library)"
    )


class TALibIndicatorCalculator(BaseFeatureCalculator):
    """Computes comprehensive technical indicators using TA-Lib.

    Indicator Groups:
    - Momentum: RSI, MACD, Stochastic, ADX, CCI, Williams %R, MFI
    - Trend: SMA, EMA (20, 50, 200), Parabolic SAR, Ichimoku Cloud
    - Volatility: Bollinger Bands, ATR
    - Volume: OBV, VWAP
    - Support/Resistance: Pivot Points

    Requires TA-Lib system library and Python wrapper to be installed.
    """

    def __init__(
        self,
        # RSI
        rsi_period: int = 14,
        # MACD
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        # Bollinger Bands
        bb_period: int = 20,
        bb_std: float = 2.0,
        # Moving Averages
        sma_periods: tuple[int, ...] = (20, 50, 200),
        ema_periods: tuple[int, ...] = (20, 50, 200),
        # ATR
        atr_period: int = 14,
        # Stochastic
        stoch_k_period: int = 14,
        stoch_d_period: int = 3,
        stoch_slowing: int = 3,
        # ADX
        adx_period: int = 14,
        # CCI
        cci_period: int = 20,
        # Williams %R
        willr_period: int = 14,
        # MFI
        mfi_period: int = 14,
        # Parabolic SAR
        sar_acceleration: float = 0.02,
        sar_maximum: float = 0.2,
        # Ichimoku
        ichi_tenkan: int = 9,
        ichi_kijun: int = 26,
        ichi_senkou_b: int = 52,
    ):
        """Initialize the TA-Lib indicator calculator.

        Args:
            rsi_period: RSI lookback period
            macd_fast: MACD fast EMA period
            macd_slow: MACD slow EMA period
            macd_signal: MACD signal line period
            bb_period: Bollinger Bands period
            bb_std: Bollinger Bands standard deviation multiplier
            sma_periods: Tuple of SMA periods to compute
            ema_periods: Tuple of EMA periods to compute
            atr_period: ATR period
            stoch_k_period: Stochastic %K period
            stoch_d_period: Stochastic %D period
            stoch_slowing: Stochastic slowing period
            adx_period: ADX period
            cci_period: CCI period
            willr_period: Williams %R period
            mfi_period: MFI period
            sar_acceleration: Parabolic SAR acceleration factor
            sar_maximum: Parabolic SAR maximum acceleration
            ichi_tenkan: Ichimoku Tenkan-sen period
            ichi_kijun: Ichimoku Kijun-sen period
            ichi_senkou_b: Ichimoku Senkou Span B period
        """
        if not TALIB_AVAILABLE:
            raise ImportError(
                "TA-Lib is required for TALibIndicatorCalculator. "
                "Install with: pip install TA-Lib (requires system TA-Lib library)"
            )

        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.sma_periods = sma_periods
        self.ema_periods = ema_periods
        self.atr_period = atr_period
        self.stoch_k_period = stoch_k_period
        self.stoch_d_period = stoch_d_period
        self.stoch_slowing = stoch_slowing
        self.adx_period = adx_period
        self.cci_period = cci_period
        self.willr_period = willr_period
        self.mfi_period = mfi_period
        self.sar_acceleration = sar_acceleration
        self.sar_maximum = sar_maximum
        self.ichi_tenkan = ichi_tenkan
        self.ichi_kijun = ichi_kijun
        self.ichi_senkou_b = ichi_senkou_b

    @property
    def feature_specs(self) -> list[FeatureSpec]:
        """Return list of feature specifications this calculator produces."""
        specs = [
            # Momentum indicators
            FeatureSpec("rsi_14", "Relative Strength Index (14)", self.rsi_period + 1, "momentum"),
            FeatureSpec("macd", "MACD Line", self.macd_slow, "momentum"),
            FeatureSpec("macd_signal", "MACD Signal Line", self.macd_slow + self.macd_signal, "momentum"),
            FeatureSpec("macd_hist", "MACD Histogram", self.macd_slow + self.macd_signal, "momentum"),
            FeatureSpec("stoch_k", "Stochastic %K", self.stoch_k_period + self.stoch_slowing, "momentum"),
            FeatureSpec("stoch_d", "Stochastic %D", self.stoch_k_period + self.stoch_slowing + self.stoch_d_period, "momentum"),
            FeatureSpec("adx_14", "Average Directional Index (14)", self.adx_period * 2, "momentum"),
            FeatureSpec("cci_20", "Commodity Channel Index (20)", self.cci_period, "momentum"),
            FeatureSpec("willr_14", "Williams %R (14)", self.willr_period, "momentum"),
            FeatureSpec("mfi_14", "Money Flow Index (14)", self.mfi_period + 1, "momentum"),
            # Trend indicators
            FeatureSpec("psar", "Parabolic SAR", 2, "trend"),
            FeatureSpec("ichi_tenkan", "Ichimoku Tenkan-sen", self.ichi_tenkan, "trend"),
            FeatureSpec("ichi_kijun", "Ichimoku Kijun-sen", self.ichi_kijun, "trend"),
            FeatureSpec("ichi_senkou_a", "Ichimoku Senkou Span A", self.ichi_kijun, "trend"),
            FeatureSpec("ichi_senkou_b", "Ichimoku Senkou Span B", self.ichi_senkou_b, "trend"),
            FeatureSpec("ichi_chikou", "Ichimoku Chikou Span", 1, "trend"),
            # Volatility indicators
            FeatureSpec("bb_upper", "Bollinger Upper Band", self.bb_period, "volatility"),
            FeatureSpec("bb_middle", "Bollinger Middle Band", self.bb_period, "volatility"),
            FeatureSpec("bb_lower", "Bollinger Lower Band", self.bb_period, "volatility"),
            FeatureSpec("bb_width", "Bollinger Band Width", self.bb_period, "volatility"),
            FeatureSpec("bb_pct", "Bollinger %B", self.bb_period, "volatility"),
            FeatureSpec("atr_14", "Average True Range (14)", self.atr_period + 1, "volatility"),
            # Volume indicators
            FeatureSpec("obv", "On-Balance Volume", 1, "volume"),
            FeatureSpec("vwap", "Volume Weighted Average Price", 1, "volume"),
            # Support/Resistance
            FeatureSpec("pivot_pp", "Pivot Point", 1, "support_resistance"),
            FeatureSpec("pivot_r1", "Resistance 1", 1, "support_resistance"),
            FeatureSpec("pivot_r2", "Resistance 2", 1, "support_resistance"),
            FeatureSpec("pivot_s1", "Support 1", 1, "support_resistance"),
            FeatureSpec("pivot_s2", "Support 2", 1, "support_resistance"),
            # Directional indicators
            FeatureSpec("plus_di_14", "Plus Directional Indicator (14)", self.adx_period * 2, "directional"),
            FeatureSpec("minus_di_14", "Minus Directional Indicator (14)", self.adx_period * 2, "directional"),
            FeatureSpec("aroon_up_25", "Aroon Up (25)", 26, "directional"),
            FeatureSpec("aroon_down_25", "Aroon Down (25)", 26, "directional"),
            # Additional oscillators
            FeatureSpec("apo", "Absolute Price Oscillator (12,26)", 26, "momentum"),
            FeatureSpec("trix_15", "TRIX (15)", 16, "momentum"),
            FeatureSpec("ppo", "Percentage Price Oscillator (12,26)", 26, "momentum"),
            FeatureSpec("ppo_signal", "PPO Signal (9)", 35, "momentum"),
            FeatureSpec("cmo_14", "Chande Momentum Oscillator (14)", 15, "momentum"),
            FeatureSpec("rsi_2", "RSI (2) Quick", 3, "momentum"),
            FeatureSpec("roc_10", "Rate of Change (10)", 11, "momentum"),
            FeatureSpec("mom_10", "Momentum (10)", 11, "momentum"),
            # Additional overlap/trend
            FeatureSpec("kama_30", "Kaufman Adaptive MA (30)", 31, "trend"),
            FeatureSpec("ht_trendline", "Hilbert Transform Trendline", 64, "trend"),
            FeatureSpec("linearreg_slope_20", "Linear Regression Slope (20)", 20, "trend"),
            # Statistics
            FeatureSpec("stddev_20", "Standard Deviation (20)", 20, "statistics"),
            # Volume flow
            FeatureSpec("adosc", "Accumulation/Distribution Oscillator (3,10)", 11, "volume"),
            # Derived composites
            FeatureSpec("donchian_high_20", "Donchian High (20)", 20, "derived"),
            FeatureSpec("donchian_low_20", "Donchian Low (20)", 20, "derived"),
            FeatureSpec("donchian_mid_20", "Donchian Mid (20)", 20, "derived"),
            FeatureSpec("donchian_high_10", "Donchian High (10)", 10, "derived"),
            FeatureSpec("donchian_low_10", "Donchian Low (10)", 10, "derived"),
            FeatureSpec("atr_sma_50", "ATR SMA (50)", 65, "derived"),
            FeatureSpec("obv_sma_20", "OBV SMA (20)", 21, "derived"),
            FeatureSpec("obv_high_20", "OBV 20-bar High", 20, "derived"),
            FeatureSpec("obv_low_20", "OBV 20-bar Low", 20, "derived"),
            FeatureSpec("typical_price_sma_20", "Typical Price SMA (20)", 20, "derived"),
            FeatureSpec("volume_sma_20", "Volume SMA (20)", 20, "derived"),
            FeatureSpec("bar_range", "Bar Range (high - low)", 1, "derived"),
            # Candlestick patterns
            FeatureSpec("cdl_engulfing", "Engulfing Pattern", 2, "pattern"),
            FeatureSpec("cdl_hammer", "Hammer", 1, "pattern"),
            FeatureSpec("cdl_shooting_star", "Shooting Star", 1, "pattern"),
            FeatureSpec("cdl_morning_star", "Morning Star", 3, "pattern"),
            FeatureSpec("cdl_evening_star", "Evening Star", 3, "pattern"),
            FeatureSpec("cdl_doji", "Doji", 1, "pattern"),
            FeatureSpec("cdl_3white_soldiers", "Three White Soldiers", 3, "pattern"),
            FeatureSpec("cdl_3black_crows", "Three Black Crows", 3, "pattern"),
            FeatureSpec("cdl_harami", "Harami", 2, "pattern"),
            FeatureSpec("cdl_marubozu", "Marubozu", 1, "pattern"),
        ]

        # Add SMA specs
        for period in self.sma_periods:
            specs.append(FeatureSpec(f"sma_{period}", f"Simple Moving Average ({period})", period, "trend"))

        # Add EMA specs
        for period in self.ema_periods:
            specs.append(FeatureSpec(f"ema_{period}", f"Exponential Moving Average ({period})", period, "trend"))

        return specs

    @property
    def max_lookback(self) -> int:
        """Maximum lookback period required by this calculator."""
        return max(
            max(self.sma_periods),
            max(self.ema_periods),
            self.ichi_senkou_b,
            self.macd_slow + self.macd_signal,
            self.adx_period * 2,
        )

    def compute(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """Compute all TA-Lib indicators from OHLCV data.

        Args:
            df: DataFrame with datetime index and columns: open, high, low, close, volume

        Returns:
            DataFrame with computed indicator columns (same index as input)
        """
        if df.empty:
            return pd.DataFrame(index=df.index)

        result = pd.DataFrame(index=df.index)

        # Compute each indicator group
        momentum_df = self._compute_momentum(df)
        trend_df = self._compute_trend(df)
        volatility_df = self._compute_volatility(df)
        volume_df = self._compute_volume(df)
        ichimoku_df = self._compute_ichimoku(df)
        pivot_df = self._compute_pivot_points(df)
        directional_df = self._compute_directional(df)
        extra_osc_df = self._compute_additional_oscillators(df)
        extra_trend_df = self._compute_additional_trend(df)
        candle_df = self._compute_candle_patterns(df)

        # Combine all results
        for features_df in [
            momentum_df, trend_df, volatility_df, volume_df, ichimoku_df, pivot_df,
            directional_df, extra_osc_df, extra_trend_df, candle_df,
        ]:
            for col in features_df.columns:
                result[col] = features_df[col]

        # Derived composites (depend on primary indicators already in result)
        derived_df = self._compute_derived(df, result)
        for col in derived_df.columns:
            result[col] = derived_df[col]

        return result

    def _compute_momentum(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute momentum indicators."""
        result = pd.DataFrame(index=df.index)

        close = df["close"].values.astype(float)
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)
        volume = df["volume"].values.astype(float)

        # RSI
        result["rsi_14"] = talib.RSI(close, timeperiod=self.rsi_period)

        # MACD
        macd, signal, hist = talib.MACD(
            close,
            fastperiod=self.macd_fast,
            slowperiod=self.macd_slow,
            signalperiod=self.macd_signal,
        )
        result["macd"] = macd
        result["macd_signal"] = signal
        result["macd_hist"] = hist

        # Stochastic
        slowk, slowd = talib.STOCH(
            high,
            low,
            close,
            fastk_period=self.stoch_k_period,
            slowk_period=self.stoch_slowing,
            slowk_matype=0,
            slowd_period=self.stoch_d_period,
            slowd_matype=0,
        )
        result["stoch_k"] = slowk
        result["stoch_d"] = slowd

        # ADX
        result["adx_14"] = talib.ADX(high, low, close, timeperiod=self.adx_period)

        # CCI
        result["cci_20"] = talib.CCI(high, low, close, timeperiod=self.cci_period)

        # Williams %R
        result["willr_14"] = talib.WILLR(high, low, close, timeperiod=self.willr_period)

        # MFI (Money Flow Index)
        result["mfi_14"] = talib.MFI(high, low, close, volume, timeperiod=self.mfi_period)

        return result

    def _compute_trend(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute trend indicators (SMA, EMA, Parabolic SAR)."""
        result = pd.DataFrame(index=df.index)

        close = df["close"].values.astype(float)
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)

        # Simple Moving Averages
        for period in self.sma_periods:
            result[f"sma_{period}"] = talib.SMA(close, timeperiod=period)

        # Exponential Moving Averages
        for period in self.ema_periods:
            result[f"ema_{period}"] = talib.EMA(close, timeperiod=period)

        # Parabolic SAR
        result["psar"] = talib.SAR(high, low, acceleration=self.sar_acceleration, maximum=self.sar_maximum)

        return result

    def _compute_volatility(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute volatility indicators (Bollinger Bands, ATR)."""
        result = pd.DataFrame(index=df.index)

        close = df["close"].values.astype(float)
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)

        # Bollinger Bands
        upper, middle, lower = talib.BBANDS(
            close,
            timeperiod=self.bb_period,
            nbdevup=self.bb_std,
            nbdevdn=self.bb_std,
            matype=0,
        )
        result["bb_upper"] = upper
        result["bb_middle"] = middle
        result["bb_lower"] = lower

        # Bollinger Band Width: (upper - lower) / middle
        with np.errstate(divide="ignore", invalid="ignore"):
            result["bb_width"] = (upper - lower) / middle
            result["bb_width"] = np.where(np.isinf(result["bb_width"]), np.nan, result["bb_width"])

        # Bollinger %B: (close - lower) / (upper - lower)
        with np.errstate(divide="ignore", invalid="ignore"):
            result["bb_pct"] = (close - lower) / (upper - lower)
            result["bb_pct"] = np.where(np.isinf(result["bb_pct"]), np.nan, result["bb_pct"])

        # ATR
        result["atr_14"] = talib.ATR(high, low, close, timeperiod=self.atr_period)

        return result

    def _compute_volume(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute volume indicators (OBV, VWAP)."""
        result = pd.DataFrame(index=df.index)

        close = df["close"].values.astype(float)
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)
        volume = df["volume"].values.astype(float)

        # On-Balance Volume
        result["obv"] = talib.OBV(close, volume)

        # VWAP (Volume Weighted Average Price)
        # Note: TA-Lib doesn't have VWAP, compute manually
        # VWAP = cumsum(typical_price * volume) / cumsum(volume)
        typical_price = (high + low + close) / 3
        cumulative_tp_vol = np.cumsum(typical_price * volume)
        cumulative_vol = np.cumsum(volume)
        with np.errstate(divide="ignore", invalid="ignore"):
            vwap = cumulative_tp_vol / cumulative_vol
            vwap = np.where(np.isinf(vwap), np.nan, vwap)
        result["vwap"] = vwap

        return result

    def _compute_ichimoku(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute Ichimoku Cloud indicators (custom implementation)."""
        result = pd.DataFrame(index=df.index)

        high = df["high"]
        low = df["low"]
        close = df["close"]

        # Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
        tenkan_high = high.rolling(window=self.ichi_tenkan).max()
        tenkan_low = low.rolling(window=self.ichi_tenkan).min()
        result["ichi_tenkan"] = (tenkan_high + tenkan_low) / 2

        # Kijun-sen (Base Line): (26-period high + 26-period low) / 2
        kijun_high = high.rolling(window=self.ichi_kijun).max()
        kijun_low = low.rolling(window=self.ichi_kijun).min()
        result["ichi_kijun"] = (kijun_high + kijun_low) / 2

        # Senkou Span A (Leading Span A): (Tenkan + Kijun) / 2 shifted 26 periods ahead
        # Note: In storage, we don't shift forward as that would extend beyond data
        # The shift is applied during visualization/strategy use
        result["ichi_senkou_a"] = (result["ichi_tenkan"] + result["ichi_kijun"]) / 2

        # Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2
        senkou_b_high = high.rolling(window=self.ichi_senkou_b).max()
        senkou_b_low = low.rolling(window=self.ichi_senkou_b).min()
        result["ichi_senkou_b"] = (senkou_b_high + senkou_b_low) / 2

        # Chikou Span (Lagging Span): Close shifted 26 periods back
        # Store current close; the lag is applied during visualization
        result["ichi_chikou"] = close

        return result

    def _compute_pivot_points(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute Pivot Points (standard floor trader pivots)."""
        result = pd.DataFrame(index=df.index)

        high = df["high"].values
        low = df["low"].values
        close = df["close"].values

        # Standard Pivot Point
        pivot = (high + low + close) / 3

        # Support and Resistance levels
        result["pivot_pp"] = pivot
        result["pivot_r1"] = 2 * pivot - low
        result["pivot_r2"] = pivot + (high - low)
        result["pivot_s1"] = 2 * pivot - high
        result["pivot_s2"] = pivot - (high - low)

        return result

    def _compute_directional(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute directional indicators (PLUS_DI, MINUS_DI, AROON)."""
        result = pd.DataFrame(index=df.index)

        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)
        close = df["close"].values.astype(float)

        result["plus_di_14"] = talib.PLUS_DI(high, low, close, timeperiod=self.adx_period)
        result["minus_di_14"] = talib.MINUS_DI(high, low, close, timeperiod=self.adx_period)

        aroon_down, aroon_up = talib.AROON(high, low, timeperiod=25)
        result["aroon_up_25"] = aroon_up
        result["aroon_down_25"] = aroon_down

        return result

    def _compute_additional_oscillators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute additional oscillators (APO, TRIX, PPO, CMO, RSI2, ROC, MOM)."""
        result = pd.DataFrame(index=df.index)

        close = df["close"].values.astype(float)

        result["apo"] = talib.APO(close, fastperiod=12, slowperiod=26, matype=1)
        result["trix_15"] = talib.TRIX(close, timeperiod=15)
        result["ppo"] = talib.PPO(close, fastperiod=12, slowperiod=26, matype=1)
        ppo_vals = result["ppo"].values.astype(float)
        result["ppo_signal"] = talib.EMA(ppo_vals, timeperiod=9)
        result["cmo_14"] = talib.CMO(close, timeperiod=14)
        result["rsi_2"] = talib.RSI(close, timeperiod=2)
        result["roc_10"] = talib.ROC(close, timeperiod=10)
        result["mom_10"] = talib.MOM(close, timeperiod=10)

        return result

    def _compute_additional_trend(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute additional trend indicators (KAMA, HT_TRENDLINE, LINEARREG_SLOPE, STDDEV, ADOSC)."""
        result = pd.DataFrame(index=df.index)

        close = df["close"].values.astype(float)
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)
        volume = df["volume"].values.astype(float)

        result["kama_30"] = talib.KAMA(close, timeperiod=30)
        result["ht_trendline"] = talib.HT_TRENDLINE(close)
        result["linearreg_slope_20"] = talib.LINEARREG_SLOPE(close, timeperiod=20)
        result["stddev_20"] = talib.STDDEV(close, timeperiod=20, nbdev=1)
        result["adosc"] = talib.ADOSC(high, low, close, volume, fastperiod=3, slowperiod=10)

        return result

    def _compute_candle_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute candlestick pattern recognition indicators."""
        result = pd.DataFrame(index=df.index)

        o = df["open"].values.astype(float)
        h = df["high"].values.astype(float)
        l = df["low"].values.astype(float)
        c = df["close"].values.astype(float)

        result["cdl_engulfing"] = talib.CDLENGULFING(o, h, l, c)
        result["cdl_hammer"] = talib.CDLHAMMER(o, h, l, c)
        result["cdl_shooting_star"] = talib.CDLSHOOTINGSTAR(o, h, l, c)
        result["cdl_morning_star"] = talib.CDLMORNINGSTAR(o, h, l, c)
        result["cdl_evening_star"] = talib.CDLEVENINGSTAR(o, h, l, c)
        result["cdl_doji"] = talib.CDLDOJI(o, h, l, c)
        result["cdl_3white_soldiers"] = talib.CDL3WHITESOLDIERS(o, h, l, c)
        result["cdl_3black_crows"] = talib.CDL3BLACKCROWS(o, h, l, c)
        result["cdl_harami"] = talib.CDLHARAMI(o, h, l, c)
        result["cdl_marubozu"] = talib.CDLMARUBOZU(o, h, l, c)

        return result

    def _compute_derived(self, df: pd.DataFrame, indicators: pd.DataFrame) -> pd.DataFrame:
        """Compute derived/composite indicators that depend on primary indicators.

        Args:
            df: Original OHLCV DataFrame
            indicators: DataFrame with already-computed primary indicators
        """
        result = pd.DataFrame(index=df.index)

        high = df["high"]
        low = df["low"]
        close = df["close"]
        volume = df["volume"].astype(float)

        # Donchian channels
        result["donchian_high_20"] = high.rolling(window=20).max()
        result["donchian_low_20"] = low.rolling(window=20).min()
        result["donchian_mid_20"] = (result["donchian_high_20"] + result["donchian_low_20"]) / 2
        result["donchian_high_10"] = high.rolling(window=10).max()
        result["donchian_low_10"] = low.rolling(window=10).min()

        # ATR SMA(50) for volatility regime detection
        if "atr_14" in indicators.columns:
            result["atr_sma_50"] = indicators["atr_14"].rolling(window=50).mean()

        # OBV derived
        if "obv" in indicators.columns:
            obv = indicators["obv"]
            result["obv_sma_20"] = obv.rolling(window=20).mean()
            result["obv_high_20"] = obv.rolling(window=20).max()
            result["obv_low_20"] = obv.rolling(window=20).min()

        # Typical price SMA (VWAP proxy)
        typical_price = (high + low + close) / 3
        result["typical_price_sma_20"] = typical_price.rolling(window=20).mean()

        # Volume SMA for spike detection
        result["volume_sma_20"] = volume.rolling(window=20).mean()

        # Bar range
        result["bar_range"] = high - low

        return result
