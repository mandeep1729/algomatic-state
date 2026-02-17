"""FastAPI router for v1 market data API endpoints with flexible time queries.

Provides OHLCV bars and computed indicators to the Go strategy engine
and other consumers via HTTP. Supports absolute time ranges, relative
lookback periods, and bar-count lookback for maximum flexibility.

Endpoints:
- GET /api/v1/marketdata             -- OHLCV bar data
- GET /api/v1/indicators             -- computed indicator values
- GET /api/v1/marketdata+indicators  -- combined bars + indicators
"""

import logging
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from src.data.database.dependencies import get_market_grpc_client
from src.data.database.models import VALID_TIMEFRAMES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["market-data-v1"])


# ---------------------------------------------------------------------------
# Lookback parsing
# ---------------------------------------------------------------------------

# Pattern: digits followed by a unit string
_LOOKBACK_PATTERN = re.compile(r"^(\d+)\s*(h|d|w|month|y)$", re.IGNORECASE)

# Maximum lookback: 5 years
_MAX_LOOKBACK_DAYS = 5 * 365


def parse_lookback(lookback_str: str) -> timedelta:
    """Parse a human-friendly lookback string into a timedelta.

    Supported formats:
        '1h'     -> 1 hour
        '30d'    -> 30 days
        '4w'     -> 4 weeks (28 days)
        '1month' -> 1 month (30 days approximation)
        '2y'     -> 2 years (730 days)

    Args:
        lookback_str: Lookback period string (e.g. '4w', '1month', '30d').

    Returns:
        timedelta representing the lookback duration.

    Raises:
        ValueError: If the format is not recognised or exceeds 5 years.
    """
    if not lookback_str or not lookback_str.strip():
        raise ValueError("Lookback string must not be empty")

    match = _LOOKBACK_PATTERN.match(lookback_str.strip())
    if not match:
        raise ValueError(
            f"Invalid lookback format '{lookback_str}'. "
            "Expected: <number><unit> where unit is h, d, w, month, or y "
            "(e.g. '4w', '1month', '30d')"
        )

    amount = int(match.group(1))
    unit = match.group(2).lower()

    if amount <= 0:
        raise ValueError(f"Lookback amount must be positive, got {amount}")

    unit_map = {
        "h": timedelta(hours=1),
        "d": timedelta(days=1),
        "w": timedelta(weeks=1),
        "month": timedelta(days=30),
        "y": timedelta(days=365),
    }

    delta = unit_map[unit] * amount

    if delta.days > _MAX_LOOKBACK_DAYS:
        raise ValueError(
            f"Lookback '{lookback_str}' exceeds maximum of 5 years "
            f"({_MAX_LOOKBACK_DAYS} days)"
        )

    logger.debug("Parsed lookback '%s' -> %s", lookback_str, delta)
    return delta


def determine_date_range(
    start: Optional[str],
    end: Optional[str],
    lookback: Optional[str],
    last_n_bars: Optional[int],
    timeframe: str,
) -> tuple[Optional[datetime], Optional[datetime], Optional[int]]:
    """Determine the effective date range from flexible query parameters.

    Priority (when multiple are specified):
        1. lookback -> end defaults to now, start = end - lookback
        2. last_n_bars -> returns (None, None, last_n_bars) for repo to handle
        3. start + end -> use as-is
        4. Nothing specified -> raise ValueError

    Args:
        start: Optional ISO-8601 start timestamp string.
        end: Optional ISO-8601 end timestamp string.
        lookback: Optional relative period (e.g. '4w', '1month').
        last_n_bars: Optional integer bar count.
        timeframe: Timeframe string (for validation context).

    Returns:
        Tuple of (start_dt, end_dt, bar_limit) where bar_limit is set only
        for last_n_bars mode and the datetimes are None in that case.

    Raises:
        ValueError: If no valid time specification is provided or if
            the parameters are invalid.
    """
    # Priority 1: lookback
    if lookback is not None:
        delta = parse_lookback(lookback)
        end_dt = _safe_parse_timestamp(end) if end else datetime.now(timezone.utc)
        start_dt = end_dt - delta
        logger.debug(
            "Lookback mode: start=%s end=%s (lookback=%s)",
            start_dt, end_dt, lookback,
        )
        return start_dt, end_dt, None

    # Priority 2: last_n_bars
    if last_n_bars is not None:
        if last_n_bars <= 0:
            raise ValueError("last_n_bars must be a positive integer")
        if last_n_bars > 100_000:
            raise ValueError("last_n_bars cannot exceed 100,000")
        logger.debug("Bar count mode: last_n_bars=%d", last_n_bars)
        return None, None, last_n_bars

    # Priority 3: start + end
    if start is not None and end is not None:
        start_dt = _safe_parse_timestamp(start)
        end_dt = _safe_parse_timestamp(end)
        if start_dt >= end_dt:
            raise ValueError("start must be before end")
        logger.debug("Absolute range mode: start=%s end=%s", start_dt, end_dt)
        return start_dt, end_dt, None

    # Priority 4: start only (end defaults to now)
    if start is not None:
        start_dt = _safe_parse_timestamp(start)
        end_dt = datetime.now(timezone.utc)
        logger.debug("Start-only mode: start=%s end=%s (defaulted)", start_dt, end_dt)
        return start_dt, end_dt, None

    raise ValueError(
        "Must specify at least one of: lookback, last_n_bars, "
        "or start (with optional end). "
        "Examples: lookback=4w, last_n_bars=500, "
        "start=2025-01-01T00:00:00Z&end=2025-02-01T00:00:00Z"
    )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class TimeRange(BaseModel):
    """Time range metadata in the response."""
    start: str
    end: str


class BarData(BaseModel):
    """Single OHLCV bar in the response."""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketDataResponse(BaseModel):
    """Response for GET /api/v1/marketdata."""
    symbol: str
    timeframe: str
    bars: list[BarData]
    total_bars: int
    range: TimeRange


class IndicatorRowData(BaseModel):
    """Single row of indicator values."""
    timestamp: str
    atr_14: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    ema_200: Optional[float] = None
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None

    model_config = ConfigDict(extra="allow")


class IndicatorsResponse(BaseModel):
    """Response for GET /api/v1/indicators."""
    symbol: str
    timeframe: str
    indicators: list[dict]
    total_rows: int
    range: TimeRange
    missing_indicators: list[str]


class CombinedResponse(BaseModel):
    """Response for GET /api/v1/marketdata+indicators."""
    symbol: str
    timeframe: str
    bars: list[BarData]
    indicators: list[dict]
    total_bars: int
    total_indicator_rows: int
    range: TimeRange
    missing_indicators: list[str]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_TIMESTAMP_FORMATS = [
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
]


def _safe_parse_timestamp(value: str) -> datetime:
    """Parse an ISO-format timestamp, returning a UTC-aware datetime.

    Args:
        value: Timestamp string in ISO-8601 or related format.

    Returns:
        UTC-aware datetime.

    Raises:
        ValueError: If none of the known formats match.
    """
    for fmt in _TIMESTAMP_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    raise ValueError(
        f"Cannot parse timestamp '{value}'. "
        "Use ISO format (e.g. 2024-01-01T00:00:00Z)."
    )


def _validate_timeframe(timeframe: str) -> None:
    """Raise HTTPException 400 if timeframe is not valid."""
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid timeframe '{timeframe}'. "
                f"Must be one of: {sorted(VALID_TIMEFRAMES)}"
            ),
        )


def _resolve_date_range(
    start: Optional[str],
    end: Optional[str],
    lookback: Optional[str],
    last_n_bars: Optional[int],
    timeframe: str,
) -> tuple[Optional[datetime], Optional[datetime], Optional[int]]:
    """Wrapper around determine_date_range that converts errors to HTTP 400."""
    try:
        return determine_date_range(start, end, lookback, last_n_bars, timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _bars_df_to_list(df) -> list[BarData]:
    """Convert a bars DataFrame (datetime index, OHLCV columns) to BarData list."""
    bars = []
    for ts, row in df.iterrows():
        bars.append(BarData(
            timestamp=ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
        ))
    return bars


def _features_df_to_list(df) -> tuple[list[dict], list[str]]:
    """Convert a features DataFrame to a list of dicts and collect indicator names.

    Returns:
        Tuple of (indicator_rows, all_indicator_names_sorted).
    """
    all_names: set[str] = set()
    rows: list[dict] = []
    for ts, row in df.iterrows():
        entry: dict = {
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
        }
        for col_name, value in row.items():
            if isinstance(value, (int, float)) and not math.isnan(value) and not math.isinf(value):
                entry[str(col_name)] = float(value)
                all_names.add(str(col_name))
        rows.append(entry)
    return rows, sorted(all_names)


def _make_time_range(df) -> TimeRange:
    """Build a TimeRange from a DataFrame's index min/max."""
    idx_min = df.index.min()
    idx_max = df.index.max()
    return TimeRange(
        start=idx_min.isoformat() if hasattr(idx_min, "isoformat") else str(idx_min),
        end=idx_max.isoformat() if hasattr(idx_max, "isoformat") else str(idx_max),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/marketdata", response_model=MarketDataResponse)
async def get_marketdata(
    symbol: str = Query(..., description="Ticker symbol (e.g. AAPL)"),
    timeframe: str = Query(..., description="Bar timeframe (e.g. 15Min, 1Hour, 1Day)"),
    start: Optional[str] = Query(None, description="Start timestamp (ISO-8601)"),
    end: Optional[str] = Query(None, description="End timestamp (ISO-8601)"),
    lookback: Optional[str] = Query(None, description="Relative lookback (e.g. 4w, 1month, 30d)"),
    last_n_bars: Optional[int] = Query(None, description="Number of most recent bars to fetch"),
    repo=Depends(get_market_grpc_client),
) -> MarketDataResponse:
    """Return OHLCV bars for a symbol/timeframe with flexible time queries.

    Supports three query styles (first match wins):
        1. lookback  -- relative period from now (or from 'end')
        2. last_n_bars -- fetch the N most recent bars
        3. start + end -- absolute date range (end defaults to now if omitted)

    Bars are ordered by timestamp ascending.
    """
    _validate_timeframe(timeframe)
    start_dt, end_dt, bar_limit = _resolve_date_range(
        start, end, lookback, last_n_bars, timeframe,
    )

    logger.debug(
        "GET /api/v1/marketdata symbol=%s timeframe=%s start=%s end=%s limit=%s",
        symbol, timeframe, start_dt, end_dt, bar_limit,
    )

    ticker = repo.get_ticker(symbol)
    if ticker is None:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol.upper()}' not found",
        )

    if bar_limit is not None:
        # Fetch last N bars: query descending then reverse
        df = repo.get_bars(symbol, timeframe, limit=bar_limit)
    else:
        df = repo.get_bars(symbol, timeframe, start=start_dt, end=end_dt)

    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No bars found for {symbol.upper()}/{timeframe} in the given range",
        )

    bars = _bars_df_to_list(df)
    time_range = _make_time_range(df)

    logger.info(
        "Served %d bars for %s/%s (%s to %s)",
        len(bars), symbol.upper(), timeframe, time_range.start, time_range.end,
    )

    return MarketDataResponse(
        symbol=symbol.upper(),
        timeframe=timeframe,
        bars=bars,
        total_bars=len(bars),
        range=time_range,
    )


@router.get("/indicators", response_model=IndicatorsResponse)
async def get_indicators(
    symbol: str = Query(..., description="Ticker symbol (e.g. AAPL)"),
    timeframe: str = Query(..., description="Bar timeframe (e.g. 15Min, 1Hour, 1Day)"),
    start: Optional[str] = Query(None, description="Start timestamp (ISO-8601)"),
    end: Optional[str] = Query(None, description="End timestamp (ISO-8601)"),
    lookback: Optional[str] = Query(None, description="Relative lookback (e.g. 4w, 1month, 30d)"),
    last_n_bars: Optional[int] = Query(None, description="Number of most recent indicator rows"),
    indicators: Optional[str] = Query(None, description="Comma-separated indicator subset (e.g. atr_14,sma_20,rsi_14)"),
    repo=Depends(get_market_grpc_client),
) -> IndicatorsResponse:
    """Return computed indicator values for a symbol/timeframe with flexible time queries.

    Supports the same three query styles as /api/v1/marketdata.
    Optionally filter returned indicators with the 'indicators' parameter.
    Rows are ordered by timestamp ascending.
    """
    _validate_timeframe(timeframe)
    start_dt, end_dt, bar_limit = _resolve_date_range(
        start, end, lookback, last_n_bars, timeframe,
    )

    # Parse optional indicator filter
    requested_indicators: Optional[set[str]] = None
    if indicators:
        requested_indicators = {name.strip() for name in indicators.split(",") if name.strip()}
        logger.debug("Indicator filter: %s", requested_indicators)

    logger.debug(
        "GET /api/v1/indicators symbol=%s timeframe=%s start=%s end=%s limit=%s",
        symbol, timeframe, start_dt, end_dt, bar_limit,
    )

    ticker = repo.get_ticker(symbol)
    if ticker is None:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol.upper()}' not found",
        )

    features_df = repo.get_features(symbol, timeframe, start=start_dt, end=end_dt)

    if features_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No indicators found for {symbol.upper()}/{timeframe} in the given range",
        )

    # Apply bar limit if in last_n_bars mode (take tail)
    if bar_limit is not None and len(features_df) > bar_limit:
        features_df = features_df.tail(bar_limit)

    # Filter to requested indicator columns if specified
    missing_indicators: list[str] = []
    if requested_indicators:
        available_cols = set(features_df.columns)
        missing_indicators = sorted(requested_indicators - available_cols)
        keep_cols = sorted(requested_indicators & available_cols)
        if keep_cols:
            features_df = features_df[keep_cols]
        # If no matching columns at all, still return rows with timestamps only

    indicator_rows, all_names = _features_df_to_list(features_df)
    time_range = _make_time_range(features_df)

    logger.info(
        "Served %d indicator rows (%d indicators) for %s/%s",
        len(indicator_rows), len(all_names), symbol.upper(), timeframe,
    )

    return IndicatorsResponse(
        symbol=symbol.upper(),
        timeframe=timeframe,
        indicators=indicator_rows,
        total_rows=len(indicator_rows),
        range=time_range,
        missing_indicators=missing_indicators,
    )


@router.get("/marketdata+indicators", response_model=CombinedResponse)
async def get_marketdata_and_indicators(
    symbol: str = Query(..., description="Ticker symbol (e.g. AAPL)"),
    timeframe: str = Query(..., description="Bar timeframe (e.g. 15Min, 1Hour, 1Day)"),
    start: Optional[str] = Query(None, description="Start timestamp (ISO-8601)"),
    end: Optional[str] = Query(None, description="End timestamp (ISO-8601)"),
    lookback: Optional[str] = Query(None, description="Relative lookback (e.g. 4w, 1month, 30d)"),
    last_n_bars: Optional[int] = Query(None, description="Number of most recent bars/rows"),
    indicators: Optional[str] = Query(None, description="Comma-separated indicator subset"),
    repo=Depends(get_market_grpc_client),
) -> CombinedResponse:
    """Return both OHLCV bars and indicators aligned by timestamp.

    Combines the data from /api/v1/marketdata and /api/v1/indicators
    in a single response. Supports the same flexible query parameters.
    """
    _validate_timeframe(timeframe)
    start_dt, end_dt, bar_limit = _resolve_date_range(
        start, end, lookback, last_n_bars, timeframe,
    )

    # Parse optional indicator filter
    requested_indicators: Optional[set[str]] = None
    if indicators:
        requested_indicators = {name.strip() for name in indicators.split(",") if name.strip()}

    logger.debug(
        "GET /api/v1/marketdata+indicators symbol=%s timeframe=%s start=%s end=%s limit=%s",
        symbol, timeframe, start_dt, end_dt, bar_limit,
    )

    ticker = repo.get_ticker(symbol)
    if ticker is None:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol.upper()}' not found",
        )

    if bar_limit is not None:
        bars_df = repo.get_bars(symbol, timeframe, limit=bar_limit)
        features_df = repo.get_features(symbol, timeframe)
    else:
        bars_df = repo.get_bars(symbol, timeframe, start=start_dt, end=end_dt)
        features_df = repo.get_features(symbol, timeframe, start=start_dt, end=end_dt)

    if bars_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for {symbol.upper()}/{timeframe} in the given range",
        )

    # Apply bar limit to features if needed
    if bar_limit is not None and not features_df.empty and len(features_df) > bar_limit:
        features_df = features_df.tail(bar_limit)

    # Filter indicators if requested
    missing_indicators: list[str] = []
    if requested_indicators and not features_df.empty:
        available_cols = set(features_df.columns)
        missing_indicators = sorted(requested_indicators - available_cols)
        keep_cols = sorted(requested_indicators & available_cols)
        if keep_cols:
            features_df = features_df[keep_cols]

    bars = _bars_df_to_list(bars_df)
    time_range = _make_time_range(bars_df)

    indicator_rows: list[dict] = []
    if not features_df.empty:
        indicator_rows, _ = _features_df_to_list(features_df)

    logger.info(
        "Served %d bars + %d indicator rows for %s/%s",
        len(bars), len(indicator_rows), symbol.upper(), timeframe,
    )

    return CombinedResponse(
        symbol=symbol.upper(),
        timeframe=timeframe,
        bars=bars,
        indicators=indicator_rows,
        total_bars=len(bars),
        total_indicator_rows=len(indicator_rows),
        range=time_range,
        missing_indicators=missing_indicators,
    )
