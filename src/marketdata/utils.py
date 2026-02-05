"""Shared utilities for market data providers."""

import logging
import time
from datetime import datetime, timedelta
from typing import Callable, TypeVar

import pandas as pd

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, calls_per_minute: int = 200):
        self.calls_per_minute = calls_per_minute
        self.min_interval = 60.0 / calls_per_minute
        self.last_call_time = 0.0

    def wait(self) -> None:
        """Wait if necessary to respect rate limits."""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call_time = time.time()


def fetch_with_retry(
    fn: Callable[[], T],
    max_retries: int = 3,
    rate_limiter: RateLimiter | None = None,
) -> T:
    """Call fn with exponential backoff retry.

    Args:
        fn: Zero-argument callable to invoke.
        max_retries: Maximum number of attempts.
        rate_limiter: Optional rate limiter to wait on before each attempt.

    Returns:
        The return value of fn.

    Raises:
        RuntimeError: If all attempts fail.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            if rate_limiter is not None:
                rate_limiter.wait()
            return fn()
        except Exception as e:
            last_error = e
            logger.debug(
                "Fetch attempt %d/%d failed: %s",
                attempt + 1, max_retries, str(e)
            )
            if attempt < max_retries - 1:
                delay = 2**attempt
                logger.debug("Retrying in %d seconds", delay)
                time.sleep(delay)

    logger.error("All %d fetch attempts failed: %s", max_retries, str(last_error))
    raise RuntimeError(f"Failed after {max_retries} attempts: {last_error}")


def generate_date_chunks(
    start: datetime,
    end: datetime,
    max_days: int,
) -> list[tuple[datetime, datetime]]:
    """Split a date range into chunks of at most max_days.

    Args:
        start: Range start (inclusive).
        end: Range end (inclusive).
        max_days: Maximum days per chunk.

    Returns:
        List of (chunk_start, chunk_end) tuples.
    """
    chunks: list[tuple[datetime, datetime]] = []
    current = start
    while current < end:
        chunk_end = min(current + timedelta(days=max_days), end)
        chunks.append((current, chunk_end))
        current = chunk_end
    return chunks


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure standard OHLCV columns and a timezone-naive datetime index.

    Selects only open/high/low/close/volume columns, sets the index name
    to ``timestamp``, and strips timezone info from the index.

    Args:
        df: Raw DataFrame containing at least OHLCV columns.

    Returns:
        Cleaned DataFrame.

    Raises:
        ValueError: If any required OHLCV column is missing.
    """
    logger.debug("Normalizing OHLCV data: %d rows, columns=%s", len(df), df.columns.tolist())
    ohlcv_cols = ["open", "high", "low", "close", "volume"]
    missing = [c for c in ohlcv_cols if c not in df.columns]
    if missing:
        logger.error("Missing required OHLCV columns: %s", missing)
        raise ValueError(f"Missing required columns: {missing}. Found: {df.columns.tolist()}")

    df = df[ohlcv_cols].copy()
    df.index.name = "timestamp"
    df = ensure_timezone_naive(df)
    return df


def ensure_timezone_naive(df: pd.DataFrame) -> pd.DataFrame:
    """Strip timezone information from a DataFrame's index.

    Args:
        df: DataFrame whose index may be timezone-aware.

    Returns:
        DataFrame with a timezone-naive index (no copy if already naive).
    """
    if df.index.tz is not None:
        df = df.copy()
        df.index = df.index.tz_localize(None)
    return df
