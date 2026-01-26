"""Data validation schemas for OHLCV data using pandera."""

import pandera.pandas as pa
from pandera.typing.pandas import DataFrame, Index, Series


class OHLCVSchema(pa.DataFrameModel):
    """Schema for OHLCV (Open, High, Low, Close, Volume) market data.

    Validates:
    - Required columns with correct dtypes
    - High >= max(open, close)
    - Low <= min(open, close)
    - Positive prices
    - Non-negative volume
    """

    timestamp: Index[pa.DateTime] = pa.Field(coerce=True)
    open: Series[float] = pa.Field(gt=0, coerce=True)
    high: Series[float] = pa.Field(gt=0, coerce=True)
    low: Series[float] = pa.Field(gt=0, coerce=True)
    close: Series[float] = pa.Field(gt=0, coerce=True)
    volume: Series[int] = pa.Field(ge=0, coerce=True)

    @pa.check("high", name="high_gte_open_close")
    def high_gte_open_close(cls, high: Series[float]) -> Series[bool]:
        """High must be >= both open and close."""
        # This check will be evaluated in context of the dataframe
        return high >= high  # Placeholder - actual check done in dataframe_check

    @pa.check("low", name="low_lte_open_close")
    def low_lte_open_close(cls, low: Series[float]) -> Series[bool]:
        """Low must be <= both open and close."""
        return low <= low  # Placeholder - actual check done in dataframe_check

    @pa.dataframe_check
    def high_low_consistency(cls, df: DataFrame) -> Series[bool]:
        """Validate high >= max(open, close) and low <= min(open, close)."""
        high_valid = df["high"] >= df[["open", "close"]].max(axis=1)
        low_valid = df["low"] <= df[["open", "close"]].min(axis=1)
        return high_valid & low_valid

    class Config:
        strict = False  # Allow extra columns
        coerce = True
        ordered = False


def validate_ohlcv(df: DataFrame) -> DataFrame:
    """Validate a DataFrame against the OHLCV schema.

    Args:
        df: DataFrame to validate

    Returns:
        Validated DataFrame

    Raises:
        pandera.errors.SchemaError: If validation fails
    """
    return OHLCVSchema.validate(df)
