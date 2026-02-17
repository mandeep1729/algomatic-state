"""FastAPI router for strategy probe analysis.

Provides endpoints for:
- Weekly strategy theme performance rankings by ticker symbol
- Strategy details by theme (strategy_type)

Data source: strategy_probe_results table (simulated strategies),
joined with probe_strategies for strategy_type (theme).
Groups by strategy_type, NOT individual strategies.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.auth_middleware import get_current_user
from src.data.database.dependencies import get_probe_repo
from src.data.database.probe_repository import ProbeRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strategy-probe", tags=["strategy-probe"])


# -----------------------------------------------------------------------------
# Response Models
# -----------------------------------------------------------------------------

class ThemeRanking(BaseModel):
    """A strategy theme's performance within a week."""
    theme: str
    num_trades: int
    num_profitable: int = 0
    num_unprofitable: int = 0
    num_long: int = 0
    num_short: int = 0
    avg_pnl_per_trade: float
    weighted_avg_pnl: float
    rank: int
    top_strategy_name: str = ""


class WeekPerformance(BaseModel):
    """Theme rankings for a single week."""
    week_start: str
    week_end: str
    themes: list[ThemeRanking]


class StrategyProbeResponse(BaseModel):
    """Full strategy probe response for a symbol."""
    symbol: str
    weeks: list[WeekPerformance]
    available_timeframes: list[str] = []


class ThemeStrategyDetail(BaseModel):
    """Details of a single strategy within a theme."""
    display_name: str
    name: str
    philosophy: str
    direction: str
    details: dict[str, Any]


class ThemeStrategiesResponse(BaseModel):
    """All strategies belonging to a theme (strategy_type)."""
    strategy_type: str
    strategies: list[ThemeStrategyDetail]


class TopStrategyDetail(BaseModel):
    """A top strategy for a theme in a specific week, with performance + details."""
    display_name: str
    name: str
    philosophy: str
    direction: str
    details: dict[str, Any]
    num_trades: int
    num_profitable: int = 0
    num_unprofitable: int = 0
    weighted_avg_pnl: float
    avg_pnl_per_trade: float


class TopStrategiesResponse(BaseModel):
    """Top strategies for a theme within a specific week."""
    strategy_type: str
    week_start: str
    week_end: str
    strategies: list[TopStrategyDetail]


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get("/strategies/{strategy_type}", response_model=ThemeStrategiesResponse)
async def get_theme_strategies(
    strategy_type: str,
    user_id: int = Depends(get_current_user),
    repo: ProbeRepository = Depends(get_probe_repo),
):
    """Get all strategies for a given theme (strategy_type).

    Returns strategy details including display name, philosophy, direction,
    and entry/exit conditions from the details JSON column.
    """
    logger.info(
        "Theme strategies request: strategy_type=%s, user_id=%d",
        strategy_type, user_id,
    )

    strategies = repo.list_strategies_by_type(strategy_type)
    logger.debug("Found %d strategies for theme=%s", len(strategies), strategy_type)

    if not strategies:
        logger.info("No strategies found for strategy_type=%s", strategy_type)
        raise HTTPException(
            status_code=404,
            detail=f"No strategies found for theme '{strategy_type}'",
        )

    result = [
        ThemeStrategyDetail(
            display_name=s.display_name,
            name=s.name,
            philosophy=s.philosophy,
            direction=s.direction,
            details=s.details or {},
        )
        for s in strategies
    ]

    logger.info(
        "Theme strategies complete: strategy_type=%s, count=%d",
        strategy_type, len(result),
    )

    return ThemeStrategiesResponse(
        strategy_type=strategy_type,
        strategies=result,
    )

@router.get("/top-strategies/{symbol}/{strategy_type}", response_model=TopStrategiesResponse)
async def get_top_strategies(
    symbol: str,
    strategy_type: str,
    week_start: date = Query(..., description="Week start date (ISO)"),
    week_end: date = Query(..., description="Week end date (ISO)"),
    timeframe: Optional[str] = Query(None, description="Filter by timeframe"),
    user_id: int = Depends(get_current_user),
    repo: ProbeRepository = Depends(get_probe_repo),
):
    """Get top 3 strategies for a theme within a specific week."""
    symbol = symbol.upper()
    logger.info(
        "Top strategies request: symbol=%s, theme=%s, week=%s to %s, tf=%s, user=%d",
        symbol, strategy_type, week_start, week_end, timeframe, user_id,
    )

    rows = repo.get_top_strategies(
        symbol=symbol,
        strategy_type=strategy_type,
        week_start=week_start,
        week_end=week_end,
        timeframe=timeframe,
        limit=3,
    )

    strategies = []
    for row in rows:
        total_trades = row["total_trades"]
        sum_pnl = row["sum_pnl"]
        avg_pnl = sum_pnl / total_trades if total_trades > 0 else 0.0

        strategies.append(TopStrategyDetail(
            display_name=row["display_name"],
            name=row["name"],
            philosophy=row["philosophy"],
            direction=row["direction"],
            details=row["details"],
            num_trades=total_trades,
            num_profitable=row["profitable_trades"],
            num_unprofitable=row["unprofitable_trades"],
            weighted_avg_pnl=round(sum_pnl, 2),
            avg_pnl_per_trade=round(avg_pnl, 2),
        ))

    logger.info(
        "Top strategies complete: symbol=%s, theme=%s, found=%d",
        symbol, strategy_type, len(strategies),
    )

    return TopStrategiesResponse(
        strategy_type=strategy_type,
        week_start=week_start.isoformat(),
        week_end=week_end.isoformat(),
        strategies=strategies,
    )


@router.get("/{symbol}", response_model=StrategyProbeResponse)
async def get_strategy_probe(
    symbol: str,
    start_date: Optional[date] = Query(None, description="Start date (inclusive)"),
    end_date: Optional[date] = Query(None, description="End date (inclusive)"),
    timeframe: Optional[str] = Query(None, description="Filter by timeframe (e.g. 1Min, 5Min, 1Hour)"),
    direction: Optional[str] = Query(None, description="Filter by trade direction (long, short)"),
    user_id: int = Depends(get_current_user),
    repo: ProbeRepository = Depends(get_probe_repo),
):
    """Get weekly strategy theme rankings for a given symbol."""
    symbol = symbol.upper()
    logger.info(
        "Strategy probe request: symbol=%s, start=%s, end=%s, timeframe=%s, direction=%s, user_id=%d",
        symbol, start_date, end_date, timeframe, direction, user_id,
    )

    available_timeframes = repo.get_available_timeframes(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        direction=direction,
    )
    logger.debug("Available timeframes for %s: %s", symbol, available_timeframes)

    results = repo.get_weekly_theme_rankings(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
        direction=direction,
    )

    logger.debug("Found %d theme-week groups for %s", len(results), symbol)

    if not results:
        logger.info("No probe results found for symbol=%s in date range", symbol)
        return StrategyProbeResponse(
            symbol=symbol, weeks=[], available_timeframes=available_timeframes,
        )

    # Find top strategy per (week, theme)
    top_strategy_names = repo.get_top_strategy_names_by_week(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
        direction=direction,
    )

    logger.debug("Found top strategies for %d week-theme groups", len(top_strategy_names))

    # Group results by (iso_year, iso_week)
    weeks_data: dict[tuple[int, int], list[dict]] = {}
    for row in results:
        iso_year = row["iso_year"]
        iso_week = row["iso_week"]
        key = (iso_year, iso_week)
        theme = row["theme"] or "unknown"

        total_trades = row["total_trades"]
        sum_pnl = row["sum_pnl"]
        avg_pnl = sum_pnl / total_trades if total_trades > 0 else 0.0

        entry = {
            "theme": theme,
            "num_trades": total_trades,
            "num_profitable": row["profitable_trades"],
            "num_unprofitable": row["unprofitable_trades"],
            "num_long": row["long_trades"],
            "num_short": row["short_trades"],
            "avg_pnl_per_trade": round(avg_pnl, 2),
            "weighted_avg_pnl": round(sum_pnl, 2),
            "top_strategy_name": top_strategy_names.get((iso_year, iso_week, theme), ""),
        }

        if key not in weeks_data:
            weeks_data[key] = []
        weeks_data[key].append(entry)

    # Build response with ranking within each week
    weeks_response: list[WeekPerformance] = []
    for (iso_year, iso_week), entries in sorted(weeks_data.items()):
        entries.sort(key=lambda e: e["weighted_avg_pnl"], reverse=True)

        ranked_entries: list[ThemeRanking] = []
        current_rank = 1
        for i, entry in enumerate(entries):
            if i > 0 and entry["weighted_avg_pnl"] != entries[i - 1]["weighted_avg_pnl"]:
                current_rank = i + 1

            ranked_entries.append(ThemeRanking(
                theme=entry["theme"],
                num_trades=entry["num_trades"],
                num_profitable=entry.get("num_profitable", 0),
                num_unprofitable=entry.get("num_unprofitable", 0),
                num_long=entry.get("num_long", 0),
                num_short=entry.get("num_short", 0),
                avg_pnl_per_trade=entry["avg_pnl_per_trade"],
                weighted_avg_pnl=entry["weighted_avg_pnl"],
                rank=current_rank,
                top_strategy_name=entry.get("top_strategy_name", ""),
            ))

        week_start = datetime.strptime(f"{iso_year}-W{iso_week:02d}-1", "%G-W%V-%u").date()
        week_end = datetime.strptime(f"{iso_year}-W{iso_week:02d}-7", "%G-W%V-%u").date()

        weeks_response.append(WeekPerformance(
            week_start=week_start.isoformat(),
            week_end=week_end.isoformat(),
            themes=ranked_entries,
        ))

    logger.info(
        "Strategy probe complete: symbol=%s, weeks=%d, total_groups=%d",
        symbol, len(weeks_response), len(results),
    )

    return StrategyProbeResponse(
        symbol=symbol, weeks=weeks_response, available_timeframes=available_timeframes,
    )


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def get_best_theme_for_trade(
    ticker: str,
    timeframe: str,
    asof_datetime: datetime,
    db,
) -> Optional[str]:
    """Get the best strategy theme for a given ticker and timeframe.

    Args:
        ticker: Ticker symbol.
        timeframe: Timeframe string.
        asof_datetime: Reference datetime.
        db: Database session.

    Returns:
        Name of the best theme (str), or None if no data found.
    """
    from src.data.database.probe_repository import ProbeRepository

    lookback_days = 3 if timeframe in ("5Min", "15Min") else 5
    repo = ProbeRepository(db)
    return repo.get_best_theme(
        ticker=ticker,
        timeframe=timeframe,
        lookback_days=lookback_days,
        asof_date=asof_datetime.date(),
    )
