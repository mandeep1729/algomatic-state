"""FastAPI router for market data API endpoints.

Provides OHLCV bars and computed indicators to the Go strategy engine
and other consumers via HTTP. This decouples downstream services from
direct database access.

Endpoints:
- GET /api/bars       -- OHLCV bar data for a symbol/timeframe/date range
- GET /api/indicators -- computed indicator values aligned to bars
"""

import logging
import math
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.data.database.connection import get_db_manager
from src.data.database.market_repository import OHLCVRepository
from src.data.database.models import VALID_TIMEFRAMES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["market-data"])


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------

class BarResponse(BaseModel):
    """Single OHLCV bar."""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class BarsResponse(BaseModel):
    """Response wrapper for bars endpoint."""
    symbol: str
    timeframe: str
    count: int
    bars: list[BarResponse]


class IndicatorRow(BaseModel):
    """Single row of indicator values keyed by indicator name."""
    timestamp: str
    indicators: dict[str, float]


class IndicatorsResponse(BaseModel):
    """Response wrapper for indicators endpoint."""
    symbol: str
    timeframe: str
    count: int
    indicator_names: list[str]
    rows: list[IndicatorRow]


# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------

def _validate_timeframe(timeframe: str) -> None:
    """Validate that the timeframe is in the accepted set.

    Args:
        timeframe: Timeframe string to validate.

    Raises:
        HTTPException: 400 if timeframe is not valid.
    """
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe '{timeframe}'. Must be one of: {sorted(VALID_TIMEFRAMES)}",
        )


def _validate_date_range(start: datetime, end: datetime) -> None:
    """Validate that start is before end.

    Args:
        start: Start timestamp.
        end: End timestamp.

    Raises:
        HTTPException: 400 if start >= end.
    """
    if start >= end:
        raise HTTPException(
            status_code=400,
            detail="start_timestamp must be before end_timestamp",
        )


def _parse_timestamp(value: str, param_name: str) -> datetime:
    """Parse an ISO-format timestamp string.

    Tries several common formats so callers can use RFC3339, ISO 8601, or
    bare dates.

    Args:
        value: Timestamp string.
        param_name: Name of the query parameter (for error messages).

    Returns:
        Parsed datetime.

    Raises:
        HTTPException: 400 if the timestamp cannot be parsed.
    """
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise HTTPException(
        status_code=400,
        detail=f"Cannot parse {param_name}='{value}'. Use ISO format (e.g. 2024-01-01T00:00:00).",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/bars", response_model=BarsResponse)
async def get_bars(
    symbol: str = Query(..., description="Ticker symbol (e.g. AAPL)"),
    timeframe: str = Query(..., description="Bar timeframe (e.g. 1Min, 15Min, 1Hour, 1Day)"),
    start_timestamp: str = Query(..., description="Start timestamp (ISO format)"),
    end_timestamp: str = Query(..., description="End timestamp (ISO format)"),
) -> BarsResponse:
    """Return OHLCV bars for a symbol/timeframe within a date range.

    Bars are ordered by timestamp ascending. Returns 404 if no data
    is found for the given parameters.
    """
    _validate_timeframe(timeframe)
    start = _parse_timestamp(start_timestamp, "start_timestamp")
    end = _parse_timestamp(end_timestamp, "end_timestamp")
    _validate_date_range(start, end)

    logger.debug(
        "GET /api/bars symbol=%s timeframe=%s start=%s end=%s",
        symbol, timeframe, start, end,
    )

    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = OHLCVRepository(session)

        # Verify symbol exists
        ticker = repo.get_ticker(symbol)
        if ticker is None:
            raise HTTPException(
                status_code=404,
                detail=f"Symbol '{symbol.upper()}' not found",
            )

        df = repo.get_bars(symbol, timeframe, start=start, end=end)

    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No bars found for {symbol.upper()}/{timeframe} in the given date range",
        )

    bars = []
    for ts, row in df.iterrows():
        bars.append(BarResponse(
            timestamp=ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
        ))

    logger.info(
        "Served %d bars for %s/%s (%s to %s)",
        len(bars), symbol.upper(), timeframe, start, end,
    )

    return BarsResponse(
        symbol=symbol.upper(),
        timeframe=timeframe,
        count=len(bars),
        bars=bars,
    )


@router.get("/indicators", response_model=IndicatorsResponse)
async def get_indicators(
    symbol: str = Query(..., description="Ticker symbol (e.g. AAPL)"),
    timeframe: str = Query(..., description="Bar timeframe (e.g. 1Min, 15Min, 1Hour, 1Day)"),
    start_timestamp: str = Query(..., description="Start timestamp (ISO format)"),
    end_timestamp: str = Query(..., description="End timestamp (ISO format)"),
) -> IndicatorsResponse:
    """Return computed indicator values for a symbol/timeframe within a date range.

    Rows are ordered by timestamp ascending and aligned with /api/bars
    timestamps. Missing or non-finite indicator values are excluded from
    the per-row dictionary to keep the payload sparse.
    """
    _validate_timeframe(timeframe)
    start = _parse_timestamp(start_timestamp, "start_timestamp")
    end = _parse_timestamp(end_timestamp, "end_timestamp")
    _validate_date_range(start, end)

    logger.debug(
        "GET /api/indicators symbol=%s timeframe=%s start=%s end=%s",
        symbol, timeframe, start, end,
    )

    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = OHLCVRepository(session)

        ticker = repo.get_ticker(symbol)
        if ticker is None:
            raise HTTPException(
                status_code=404,
                detail=f"Symbol '{symbol.upper()}' not found",
            )

        features_df = repo.get_features(symbol, timeframe, start=start, end=end)

    if features_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No indicators found for {symbol.upper()}/{timeframe} in the given date range",
        )

    # Collect all indicator names across all rows
    all_indicator_names: set[str] = set()

    rows: list[IndicatorRow] = []
    for ts, row in features_df.iterrows():
        indicators: dict[str, float] = {}
        for col_name, value in row.items():
            if isinstance(value, (int, float)) and not math.isnan(value) and not math.isinf(value):
                indicators[str(col_name)] = float(value)
                all_indicator_names.add(str(col_name))
        rows.append(IndicatorRow(
            timestamp=ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            indicators=indicators,
        ))

    logger.info(
        "Served %d indicator rows (%d indicators) for %s/%s (%s to %s)",
        len(rows), len(all_indicator_names), symbol.upper(), timeframe, start, end,
    )

    return IndicatorsResponse(
        symbol=symbol.upper(),
        timeframe=timeframe,
        count=len(rows),
        indicator_names=sorted(all_indicator_names),
        rows=rows,
    )
