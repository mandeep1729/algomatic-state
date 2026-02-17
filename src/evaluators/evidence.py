"""Evidence utility functions for evaluators.

Provides common calculations and formatting used across
multiple evaluators for building evidence.
"""

import logging
from typing import Literal, Optional, Tuple

import pandas as pd

from src.trade.evaluation import Evidence

logger = logging.getLogger(__name__)

# Numerical stability constant
EPS = 1e-9


def check_threshold(
    value: float,
    threshold: float,
    comparison: Literal["<", "<=", ">", ">="],
    metric_name: str,
    unit: Optional[str] = None,
) -> Tuple[bool, Evidence]:
    """Check if a value violates a threshold.

    Args:
        value: Current value
        threshold: Threshold to compare against
        comparison: Comparison operator
        metric_name: Name for the evidence
        unit: Optional unit of measurement

    Returns:
        Tuple of (is_violated, evidence)
    """
    comparisons = {
        "<": lambda v, t: v < t,
        "<=": lambda v, t: v <= t,
        ">": lambda v, t: v > t,
        ">=": lambda v, t: v >= t,
    }

    is_violated = comparisons[comparison](value, threshold)

    evidence = Evidence(
        metric_name=metric_name,
        value=value,
        threshold=threshold,
        comparison=comparison,
        unit=unit,
    )

    return is_violated, evidence


def compute_zscore(
    value: float,
    series: pd.Series,
    window: Optional[int] = None,
) -> Tuple[float, Evidence]:
    """Compute z-score of a value relative to a series.

    Args:
        value: Current value
        series: Historical series
        window: Rolling window size (uses all data if None)

    Returns:
        Tuple of (zscore, evidence)
    """
    logger.debug("Computing z-score: value=%.4f, window=%s, series_len=%d", value, window, len(series))
    if window is not None:
        series = series.tail(window)

    series = series.dropna()
    if len(series) < 2:
        logger.debug("Insufficient data for z-score computation: %d samples", len(series))
        return 0.0, Evidence(
            metric_name="zscore",
            value=0.0,
            context={"error": "insufficient_data"},
        )

    mean = series.mean()
    std = series.std()

    if std < EPS:
        zscore = 0.0
    else:
        zscore = (value - mean) / std

    evidence = Evidence(
        metric_name="zscore",
        value=zscore,
        context={
            "mean": float(mean),
            "std": float(std),
            "sample_size": len(series),
        },
    )

    return zscore, evidence


def compare_to_atr(
    distance: float,
    atr: float,
    metric_name: str = "distance_atr_multiple",
) -> Tuple[float, Evidence]:
    """Express a price distance as a multiple of ATR.

    Args:
        distance: Price distance (absolute)
        atr: Average True Range
        metric_name: Name for the evidence

    Returns:
        Tuple of (atr_multiple, evidence)
    """
    if atr < EPS:
        return 0.0, Evidence(
            metric_name=metric_name,
            value=0.0,
            context={"error": "atr_too_small"},
        )

    multiple = distance / atr

    evidence = Evidence(
        metric_name=metric_name,
        value=multiple,
        unit="ATR",
        context={
            "distance": distance,
            "atr": atr,
        },
    )

    return multiple, evidence


def compute_distance_to_level(
    price: float,
    level: float,
    as_percentage: bool = True,
) -> Tuple[float, Evidence]:
    """Compute distance from price to a level.

    Args:
        price: Current price
        level: Target level
        as_percentage: Return as percentage (vs absolute)

    Returns:
        Tuple of (distance, evidence)
    """
    abs_distance = abs(price - level)

    if as_percentage:
        if price < EPS:
            distance = 0.0
        else:
            distance = (abs_distance / price) * 100
        unit = "%"
    else:
        distance = abs_distance
        unit = "price"

    direction = "above" if price > level else "below"

    evidence = Evidence(
        metric_name="distance_to_level",
        value=distance,
        unit=unit,
        context={
            "price": price,
            "level": level,
            "direction": direction,
            "absolute_distance": abs_distance,
        },
    )

    return distance, evidence


def format_percentage(value: float, decimals: int = 2) -> str:
    """Format a value as a percentage string.

    Args:
        value: Value (already in percentage form)
        decimals: Number of decimal places

    Returns:
        Formatted string
    """
    return f"{value:.{decimals}f}%"


def format_currency(value: float, currency: str = "$", decimals: int = 2) -> str:
    """Format a value as currency.

    Args:
        value: Value
        currency: Currency symbol
        decimals: Number of decimal places

    Returns:
        Formatted string
    """
    if value < 0:
        return f"-{currency}{abs(value):,.{decimals}f}"
    return f"{currency}{value:,.{decimals}f}"


def format_ratio(numerator: float, denominator: float, decimals: int = 2) -> str:
    """Format a ratio as X:1.

    Args:
        numerator: Numerator value
        denominator: Denominator value
        decimals: Number of decimal places

    Returns:
        Formatted string
    """
    if denominator < EPS:
        return "∞:1"

    ratio = numerator / denominator
    return f"{ratio:.{decimals}f}:1"


