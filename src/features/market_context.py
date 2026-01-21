"""Market context features."""

from typing import Any

import pandas as pd

from .base import BaseFeatureCalculator, FeatureSpec, log_return, rolling_beta


class MarketContextFeatureCalculator(BaseFeatureCalculator):
    """Computes market context features.

    Features:
        - mkt_r5: 5-bar market return
        - mkt_r15: 15-bar market return
        - mkt_rv_60: 60-bar market realized volatility
        - beta_60: Rolling beta vs market
        - resid_rv_60: Residual volatility after market exposure

    These features stabilize regime detection and reduce false signals
    by accounting for market-wide movements.

    Requires market_df to be passed in kwargs.
    """

    def __init__(
        self,
        short_window: int = 5,
        medium_window: int = 15,
        long_window: int = 60,
    ):
        """Initialize MarketContextFeatureCalculator.

        Args:
            short_window: Short-term return window (default 5)
            medium_window: Medium-term return window (default 15)
            long_window: Long-term window for volatility and beta (default 60)
        """
        self.short_window = short_window
        self.medium_window = medium_window
        self.long_window = long_window

    @property
    def feature_specs(self) -> list[FeatureSpec]:
        return [
            FeatureSpec(
                name="mkt_r5",
                description="5-bar market return",
                lookback=self.short_window + 1,
                group="market_context",
            ),
            FeatureSpec(
                name="mkt_r15",
                description="15-bar market return",
                lookback=self.medium_window + 1,
                group="market_context",
            ),
            FeatureSpec(
                name="mkt_rv_60",
                description="60-bar market realized volatility",
                lookback=self.long_window,
                group="market_context",
            ),
            FeatureSpec(
                name="beta_60",
                description="Rolling 60-bar beta vs market",
                lookback=self.long_window,
                group="market_context",
            ),
            FeatureSpec(
                name="resid_rv_60",
                description="Residual volatility after market exposure",
                lookback=self.long_window,
                group="market_context",
            ),
        ]

    def compute(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """Compute market context features.

        Args:
            df: DataFrame with column: close (asset data)
            **kwargs:
                market_df: Required. DataFrame with column: close (market data).
                           Must have the same index as df.
                r1: Optional pre-computed asset 1-bar returns.

        Returns:
            DataFrame with columns: mkt_r5, mkt_r15, mkt_rv_60, beta_60, resid_rv_60

        Raises:
            ValueError: If market_df is not provided in kwargs.
        """
        market_df = kwargs.get("market_df")
        if market_df is None:
            raise ValueError("market_df is required for MarketContextFeatureCalculator")

        result = pd.DataFrame(index=df.index)

        # Market returns
        mkt_close = market_df["close"]
        mkt_r1 = log_return(mkt_close, periods=1)

        result["mkt_r5"] = log_return(mkt_close, periods=self.short_window)
        result["mkt_r15"] = log_return(mkt_close, periods=self.medium_window)

        # Market realized volatility
        result["mkt_rv_60"] = mkt_r1.rolling(
            window=self.long_window, min_periods=self.long_window
        ).std()

        # Get or compute asset r1
        asset_r1 = kwargs.get("r1")
        if asset_r1 is None:
            asset_r1 = log_return(df["close"], periods=1)

        # Rolling beta and residual volatility
        beta, resid_rv = rolling_beta(asset_r1, mkt_r1, window=self.long_window)
        result["beta_60"] = beta
        result["resid_rv_60"] = resid_rv

        return result
