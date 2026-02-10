"""FastAPI router for strategy probe analysis.

Provides endpoints for:
- Weekly strategy theme performance rankings by ticker symbol
- Strategy details by theme (strategy_type)

Data source: strategy_probe_results table (simulated strategies),
joined with probe_strategies for strategy_type (theme).
Groups by strategy_type, NOT individual strategies.
"""

import logging
from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from src.api.auth_middleware import get_current_user
from src.data.database.connection import get_db_manager
from src.data.database.probe_models import ProbeStrategy, StrategyProbeResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strategy-probe", tags=["strategy-probe"])


# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------

def get_db():
    """Get database session."""
    with get_db_manager().get_session() as session:
        yield session


# -----------------------------------------------------------------------------
# Response Models
# -----------------------------------------------------------------------------

class ThemeRanking(BaseModel):
    """A strategy theme's performance within a week."""
    theme: str
    num_trades: int
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
    db: Session = Depends(get_db),
):
    """Get all strategies for a given theme (strategy_type).

    Returns strategy details including display name, philosophy, direction,
    and entry/exit conditions from the details JSON column.

    Args:
        strategy_type: The theme/strategy_type to look up (e.g. trend, breakout).

    Returns:
        List of strategies with their full details for the given theme.
    """
    logger.info(
        "Theme strategies request: strategy_type=%s, user_id=%d",
        strategy_type, user_id,
    )

    strategies = (
        db.query(ProbeStrategy)
        .filter(
            ProbeStrategy.strategy_type == strategy_type,
            ProbeStrategy.is_active == True,
        )
        .order_by(ProbeStrategy.display_name.asc())
        .all()
    )

    logger.debug(
        "Found %d strategies for theme=%s", len(strategies), strategy_type,
    )

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
    db: Session = Depends(get_db),
):
    """Get top 3 strategies for a theme within a specific week.

    Queries strategy_probe_results grouped by individual strategy_id for
    the given symbol, theme, and week. Returns up to 3 strategies ranked
    by weighted average PnL, with full strategy details (philosophy, entry/exit).

    Args:
        symbol: Ticker symbol.
        strategy_type: Theme (e.g. trend, breakout).
        week_start: Start of the week (inclusive).
        week_end: End of the week (inclusive).
        timeframe: Optional timeframe filter.

    Returns:
        Top 3 strategies with performance metrics and details.
    """
    symbol = symbol.upper()
    logger.info(
        "Top strategies request: symbol=%s, theme=%s, week=%s to %s, tf=%s, user=%d",
        symbol, strategy_type, week_start, week_end, timeframe, user_id,
    )

    query = db.query(
        ProbeStrategy.id,
        ProbeStrategy.display_name,
        ProbeStrategy.name,
        ProbeStrategy.philosophy,
        ProbeStrategy.direction,
        ProbeStrategy.details,
        func.sum(StrategyProbeResult.num_trades).label("total_trades"),
        func.sum(StrategyProbeResult.num_trades * StrategyProbeResult.pnl_mean).label("sum_pnl"),
    ).join(
        StrategyProbeResult, StrategyProbeResult.strategy_id == ProbeStrategy.id,
    ).filter(
        StrategyProbeResult.symbol == symbol,
        ProbeStrategy.strategy_type == strategy_type,
        StrategyProbeResult.open_day >= week_start,
        StrategyProbeResult.open_day <= week_end,
    )

    if timeframe:
        query = query.filter(StrategyProbeResult.timeframe == timeframe)

    rows = (
        query
        .group_by(
            ProbeStrategy.id,
            ProbeStrategy.display_name,
            ProbeStrategy.name,
            ProbeStrategy.philosophy,
            ProbeStrategy.direction,
            ProbeStrategy.details,
        )
        .order_by(func.sum(StrategyProbeResult.num_trades * StrategyProbeResult.pnl_mean).desc())
        .limit(3)
        .all()
    )

    strategies = []
    for row in rows:
        total_trades = int(row.total_trades)
        sum_pnl = float(row.sum_pnl)
        avg_pnl = sum_pnl / total_trades if total_trades > 0 else 0.0

        strategies.append(TopStrategyDetail(
            display_name=row.display_name,
            name=row.name,
            philosophy=row.philosophy,
            direction=row.direction,
            details=row.details or {},
            num_trades=total_trades,
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
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get weekly strategy theme rankings for a given symbol.

    Queries strategy_probe_results joined with probe_strategies, grouped
    by ISO week and strategy_type (theme). Ranks themes by weighted
    average PnL descending within each week.

    Args:
        symbol: Ticker symbol to analyze.
        start_date: Start date for the analysis period (inclusive).
        end_date: End date for the analysis period (inclusive).
        timeframe: Optional timeframe filter (e.g. 1Min, 5Min, 1Hour).

    Returns:
        Weekly theme rankings with performance metrics and available timeframes.
    """
    symbol = symbol.upper()
    logger.info(
        "Strategy probe request: symbol=%s, start=%s, end=%s, timeframe=%s, user_id=%d",
        symbol, start_date, end_date, timeframe, user_id,
    )

    # Query distinct available timeframes for this symbol and date range.
    tf_query = db.query(
        StrategyProbeResult.timeframe,
    ).filter(
        StrategyProbeResult.symbol == symbol,
    )
    if start_date:
        tf_query = tf_query.filter(StrategyProbeResult.open_day >= start_date)
    if end_date:
        tf_query = tf_query.filter(StrategyProbeResult.open_day <= end_date)

    available_timeframes = sorted(
        row.timeframe for row in tf_query.distinct().all()
    )
    logger.debug("Available timeframes for %s: %s", symbol, available_timeframes)

    # Query grouped by ISO week and strategy_type (theme).
    base_query = db.query(
        extract("isoyear", StrategyProbeResult.open_day).label("iso_year"),
        extract("week", StrategyProbeResult.open_day).label("iso_week"),
        ProbeStrategy.strategy_type.label("theme"),
        func.sum(StrategyProbeResult.num_trades).label("total_trades"),
        func.sum(StrategyProbeResult.num_trades * StrategyProbeResult.pnl_mean).label("sum_pnl"),
    ).join(
        ProbeStrategy, StrategyProbeResult.strategy_id == ProbeStrategy.id,
    ).filter(
        StrategyProbeResult.symbol == symbol,
    )

    if start_date:
        base_query = base_query.filter(StrategyProbeResult.open_day >= start_date)
    if end_date:
        base_query = base_query.filter(StrategyProbeResult.open_day <= end_date)
    if timeframe:
        base_query = base_query.filter(StrategyProbeResult.timeframe == timeframe)
        logger.debug("Filtering by timeframe=%s", timeframe)

    results = (
        base_query
        .group_by(
            extract("isoyear", StrategyProbeResult.open_day),
            extract("week", StrategyProbeResult.open_day),
            ProbeStrategy.strategy_type,
        )
        .order_by(
            extract("isoyear", StrategyProbeResult.open_day).asc(),
            extract("week", StrategyProbeResult.open_day).asc(),
        )
        .all()
    )

    logger.debug("Found %d theme-week groups for %s", len(results), symbol)

    if not results:
        logger.info("No probe results found for symbol=%s in date range", symbol)
        return StrategyProbeResponse(
            symbol=symbol, weeks=[], available_timeframes=available_timeframes,
        )

    # Find top strategy per (week, theme) — grouped by individual strategy
    top_strat_query = db.query(
        extract("isoyear", StrategyProbeResult.open_day).label("iso_year"),
        extract("week", StrategyProbeResult.open_day).label("iso_week"),
        ProbeStrategy.strategy_type.label("theme"),
        ProbeStrategy.display_name,
        func.sum(StrategyProbeResult.num_trades * StrategyProbeResult.pnl_mean).label("strat_pnl"),
    ).join(
        ProbeStrategy, StrategyProbeResult.strategy_id == ProbeStrategy.id,
    ).filter(
        StrategyProbeResult.symbol == symbol,
    )

    if start_date:
        top_strat_query = top_strat_query.filter(StrategyProbeResult.open_day >= start_date)
    if end_date:
        top_strat_query = top_strat_query.filter(StrategyProbeResult.open_day <= end_date)
    if timeframe:
        top_strat_query = top_strat_query.filter(StrategyProbeResult.timeframe == timeframe)

    top_strat_rows = (
        top_strat_query
        .group_by(
            extract("isoyear", StrategyProbeResult.open_day),
            extract("week", StrategyProbeResult.open_day),
            ProbeStrategy.strategy_type,
            ProbeStrategy.id,
            ProbeStrategy.display_name,
        )
        .order_by(
            extract("isoyear", StrategyProbeResult.open_day).asc(),
            extract("week", StrategyProbeResult.open_day).asc(),
            func.sum(StrategyProbeResult.num_trades * StrategyProbeResult.pnl_mean).desc(),
        )
        .all()
    )

    # Pick best strategy per (week, theme) — first seen per group wins (ordered by PnL desc)
    top_strategy_names: dict[tuple[int, int, str], str] = {}
    for row in top_strat_rows:
        key = (int(row.iso_year), int(row.iso_week), row.theme or "unknown")
        if key not in top_strategy_names:
            top_strategy_names[key] = row.display_name

    logger.debug("Found top strategies for %d week-theme groups", len(top_strategy_names))

    # Group results by (iso_year, iso_week)
    weeks_data: dict[tuple[int, int], list[dict]] = {}
    for row in results:
        iso_year = int(row.iso_year)
        iso_week = int(row.iso_week)
        key = (iso_year, iso_week)
        theme = row.theme or "unknown"

        total_trades = int(row.total_trades)
        sum_pnl = float(row.sum_pnl)
        avg_pnl = sum_pnl / total_trades if total_trades > 0 else 0.0

        entry = {
            "theme": theme,
            "num_trades": total_trades,
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
