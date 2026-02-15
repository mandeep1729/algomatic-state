"""Pandas-TA based technical indicators calculator.

Pure Python alternative to TA-Lib that doesn't require system library installation.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from .base import BaseFeatureCalculator, FeatureSpec

logger = logging.getLogger(__name__)

# Check for pandas-ta availability
try:
    import pandas_ta as ta

    PANDAS_TA_AVAILABLE = True
except ImportError:
    PANDAS_TA_AVAILABLE = False
    logger.warning("pandas-ta not installed. Install with: pip install pandas-ta")


class PandasTAIndicatorCalculator(BaseFeatureCalculator):
    """Computes technical indicators using pandas-ta (pure Python).

    This is an alternative to TALibIndicatorCalculator that doesn't require
    the TA-Lib system library installation.

    Indicator Groups:
    - Momentum: RSI, MACD, Stochastic, ADX, CCI, Williams %R, MFI
    - Trend: SMA, EMA (20, 50, 200), Parabolic SAR, Ichimoku Cloud
    - Volatility: Bollinger Bands, ATR
    - Volume: OBV, VWAP
    - Support/Resistance: Pivot Points
    """

    def __init__(
        self,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bb_period: int = 20,
        bb_std: float = 2.0,
        sma_periods: tuple[int, ...] = (20, 50, 200),
        ema_periods: tuple[int, ...] = (20, 50, 200),
        atr_period: int = 14,
        stoch_k_period: int = 14,
        stoch_d_period: int = 3,
        adx_period: int = 14,
        cci_period: int = 20,
        willr_period: int = 14,
        mfi_period: int = 14,
        ichi_tenkan: int = 9,
        ichi_kijun: int = 26,
        ichi_senkou_b: int = 52,
    ):
        if not PANDAS_TA_AVAILABLE:
            raise ImportError("pandas-ta is required. Install with: pip install pandas-ta")

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
        self.adx_period = adx_period
        self.cci_period = cci_period
        self.willr_period = willr_period
        self.mfi_period = mfi_period
        self.ichi_tenkan = ichi_tenkan
        self.ichi_kijun = ichi_kijun
        self.ichi_senkou_b = ichi_senkou_b

    @property
    def feature_specs(self) -> list[FeatureSpec]:
        """Return list of feature specifications."""
        specs = [
            # Momentum
            FeatureSpec("rsi_14", "RSI (14)", self.rsi_period + 1, "momentum"),
            FeatureSpec("macd", "MACD Line", self.macd_slow, "momentum"),
            FeatureSpec("macd_signal", "MACD Signal", self.macd_slow + self.macd_signal, "momentum"),
            FeatureSpec("macd_hist", "MACD Histogram", self.macd_slow + self.macd_signal, "momentum"),
            FeatureSpec("stoch_k", "Stochastic %K", self.stoch_k_period, "momentum"),
            FeatureSpec("stoch_d", "Stochastic %D", self.stoch_k_period + self.stoch_d_period, "momentum"),
            FeatureSpec("adx_14", "ADX (14)", self.adx_period * 2, "momentum"),
            FeatureSpec("cci_20", "CCI (20)", self.cci_period, "momentum"),
            FeatureSpec("willr_14", "Williams %R (14)", self.willr_period, "momentum"),
            FeatureSpec("mfi_14", "MFI (14)", self.mfi_period + 1, "momentum"),
            # Trend
            FeatureSpec("psar", "Parabolic SAR", 2, "trend"),
            FeatureSpec("ichi_tenkan", "Ichimoku Tenkan", self.ichi_tenkan, "trend"),
            FeatureSpec("ichi_kijun", "Ichimoku Kijun", self.ichi_kijun, "trend"),
            FeatureSpec("ichi_senkou_a", "Ichimoku Senkou A", self.ichi_kijun, "trend"),
            FeatureSpec("ichi_senkou_b", "Ichimoku Senkou B", self.ichi_senkou_b, "trend"),
            # Volatility
            FeatureSpec("bb_upper", "BB Upper", self.bb_period, "volatility"),
            FeatureSpec("bb_middle", "BB Middle", self.bb_period, "volatility"),
            FeatureSpec("bb_lower", "BB Lower", self.bb_period, "volatility"),
            FeatureSpec("bb_width", "BB Width", self.bb_period, "volatility"),
            FeatureSpec("bb_pct", "BB %B", self.bb_period, "volatility"),
            FeatureSpec("atr_14", "ATR (14)", self.atr_period + 1, "volatility"),
            # Volume
            FeatureSpec("obv", "OBV", 1, "volume"),
            FeatureSpec("vwap", "VWAP", 1, "volume"),
            # Support/Resistance
            FeatureSpec("pivot_pp", "Pivot Point", 1, "support_resistance"),
            FeatureSpec("pivot_r1", "Resistance 1", 1, "support_resistance"),
            FeatureSpec("pivot_r2", "Resistance 2", 1, "support_resistance"),
            FeatureSpec("pivot_s1", "Support 1", 1, "support_resistance"),
            FeatureSpec("pivot_s2", "Support 2", 1, "support_resistance"),
        ]

        for period in self.sma_periods:
            specs.append(FeatureSpec(f"sma_{period}", f"SMA ({period})", period, "trend"))
        for period in self.ema_periods:
            specs.append(FeatureSpec(f"ema_{period}", f"EMA ({period})", period, "trend"))

        return specs

    @property
    def max_lookback(self) -> int:
        return max(max(self.sma_periods), max(self.ema_periods), self.ichi_senkou_b)

    def compute(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """Compute all indicators from OHLCV data."""
        if df.empty:
            return pd.DataFrame(index=df.index)

        result = pd.DataFrame(index=df.index)

        # Compute each group
        for compute_func in [
            self._compute_momentum,
            self._compute_trend,
            self._compute_volatility,
            self._compute_volume,
            self._compute_ichimoku,
            self._compute_pivot_points,
        ]:
            try:
                group_df = compute_func(df)
                for col in group_df.columns:
                    result[col] = group_df[col]
            except Exception as e:
                logger.error(
                    "Failed to compute %s indicator group: %s. Output will lack these features.",
                    compute_func.__name__, e, exc_info=True,
                )

        return result

    def _compute_momentum(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute momentum indicators using pandas-ta."""
        result = pd.DataFrame(index=df.index)

        # RSI
        rsi = ta.rsi(df["close"], length=self.rsi_period)
        if rsi is not None:
            result["rsi_14"] = rsi

        # MACD
        macd = ta.macd(df["close"], fast=self.macd_fast, slow=self.macd_slow, signal=self.macd_signal)
        if macd is not None:
            result["macd"] = macd.iloc[:, 0]  # MACD line
            result["macd_hist"] = macd.iloc[:, 1]  # Histogram
            result["macd_signal"] = macd.iloc[:, 2]  # Signal

        # Stochastic
        stoch = ta.stoch(df["high"], df["low"], df["close"], k=self.stoch_k_period, d=self.stoch_d_period)
        if stoch is not None:
            result["stoch_k"] = stoch.iloc[:, 0]
            result["stoch_d"] = stoch.iloc[:, 1]

        # ADX
        adx = ta.adx(df["high"], df["low"], df["close"], length=self.adx_period)
        if adx is not None:
            result["adx_14"] = adx.iloc[:, 0]  # ADX

        # CCI
        cci = ta.cci(df["high"], df["low"], df["close"], length=self.cci_period)
        if cci is not None:
            result["cci_20"] = cci

        # Williams %R
        willr = ta.willr(df["high"], df["low"], df["close"], length=self.willr_period)
        if willr is not None:
            result["willr_14"] = willr

        # MFI
        mfi = ta.mfi(df["high"], df["low"], df["close"], df["volume"], length=self.mfi_period)
        if mfi is not None:
            result["mfi_14"] = mfi

        return result

    def _compute_trend(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute trend indicators."""
        result = pd.DataFrame(index=df.index)

        # SMAs
        for period in self.sma_periods:
            sma = ta.sma(df["close"], length=period)
            if sma is not None:
                result[f"sma_{period}"] = sma

        # EMAs
        for period in self.ema_periods:
            ema = ta.ema(df["close"], length=period)
            if ema is not None:
                result[f"ema_{period}"] = ema

        # Parabolic SAR
        psar = ta.psar(df["high"], df["low"], df["close"])
        if psar is not None:
            # pandas-ta returns multiple columns, get the combined SAR
            result["psar"] = psar.iloc[:, 0].combine_first(psar.iloc[:, 1])

        return result

    def _compute_volatility(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute volatility indicators."""
        result = pd.DataFrame(index=df.index)

        # Bollinger Bands
        bbands = ta.bbands(df["close"], length=self.bb_period, std=self.bb_std)
        if bbands is not None:
            result["bb_lower"] = bbands.iloc[:, 0]
            result["bb_middle"] = bbands.iloc[:, 1]
            result["bb_upper"] = bbands.iloc[:, 2]
            result["bb_width"] = bbands.iloc[:, 3]
            result["bb_pct"] = bbands.iloc[:, 4]

        # ATR
        atr = ta.atr(df["high"], df["low"], df["close"], length=self.atr_period)
        if atr is not None:
            result["atr_14"] = atr

        return result

    def _compute_volume(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute volume indicators."""
        result = pd.DataFrame(index=df.index)

        # OBV
        obv = ta.obv(df["close"], df["volume"])
        if obv is not None:
            result["obv"] = obv

        # VWAP
        vwap = ta.vwap(df["high"], df["low"], df["close"], df["volume"])
        if vwap is not None:
            result["vwap"] = vwap

        return result

    def _compute_ichimoku(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute Ichimoku indicators."""
        result = pd.DataFrame(index=df.index)

        ichimoku = ta.ichimoku(df["high"], df["low"], df["close"],
                               tenkan=self.ichi_tenkan,
                               kijun=self.ichi_kijun,
                               senkou=self.ichi_senkou_b)
        if ichimoku is not None and len(ichimoku) > 0:
            ichi_df = ichimoku[0]  # First element is the DataFrame
            if "ITS_9" in ichi_df.columns:
                result["ichi_tenkan"] = ichi_df["ITS_9"]
            if "IKS_26" in ichi_df.columns:
                result["ichi_kijun"] = ichi_df["IKS_26"]
            if "ISA_9" in ichi_df.columns:
                result["ichi_senkou_a"] = ichi_df["ISA_9"]
            if "ISB_26" in ichi_df.columns:
                result["ichi_senkou_b"] = ichi_df["ISB_26"]

        return result

    def _compute_pivot_points(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute Pivot Points."""
        result = pd.DataFrame(index=df.index)

        high = df["high"].values
        low = df["low"].values
        close = df["close"].values

        pivot = (high + low + close) / 3
        result["pivot_pp"] = pivot
        result["pivot_r1"] = 2 * pivot - low
        result["pivot_r2"] = pivot + (high - low)
        result["pivot_s1"] = 2 * pivot - high
        result["pivot_s2"] = pivot - (high - low)

        return result
