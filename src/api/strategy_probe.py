"""FastAPI router for strategy probe analysis.

Provides endpoints for:
- Weekly strategy performance rankings by ticker symbol
- Strategy comparison across time periods
"""

import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, extract, case
from sqlalchemy.orm import Session

from src.api.auth_middleware import get_current_user
from src.data.database.connection import get_db_manager
from src.data.database.trade_lifecycle_models import PositionCampaign
from src.data.database.strategy_models import Strategy

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

class StrategyRanking(BaseModel):
    """A single strategy's performance within a week."""
    category: str
    theme: str
    num_trades: int
    avg_pnl_per_trade: float
    weighted_avg_pnl: float
    rank: int


class WeekPerformance(BaseModel):
    """Strategy rankings for a single week."""
    week_start: str
    week_end: str
    strategies: list[StrategyRanking]


class StrategyProbeResponse(BaseModel):
    """Full strategy probe response for a symbol."""
    symbol: str
    weeks: list[WeekPerformance]


# -----------------------------------------------------------------------------
# Endpoint
# -----------------------------------------------------------------------------

@router.get("/{symbol}", response_model=StrategyProbeResponse)
async def get_strategy_probe(
    symbol: str,
    start_date: Optional[date] = Query(None, description="Start date (inclusive)"),
    end_date: Optional[date] = Query(None, description="End date (inclusive)"),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get weekly strategy performance rankings for a given symbol.

    Analyzes closed position campaigns grouped by ISO week and strategy,
    then ranks strategies by weighted average PnL (descending) within
    each week. All strategies are included in the ranking, not just winners.

    Args:
        symbol: Ticker symbol to analyze.
        start_date: Start date for the analysis period (inclusive).
        end_date: End date for the analysis period (inclusive).

    Returns:
        Weekly strategy rankings with performance metrics.
    """
    symbol = symbol.upper()
    logger.info(
        "Strategy probe request: symbol=%s, start=%s, end=%s, user_id=%d",
        symbol, start_date, end_date, user_id,
    )

    # Build base query for closed campaigns with the given symbol
    base_query = db.query(
        extract("isoyear", PositionCampaign.closed_at).label("iso_year"),
        extract("week", PositionCampaign.closed_at).label("iso_week"),
        PositionCampaign.strategy_id,
        func.count(PositionCampaign.id).label("num_trades"),
        func.coalesce(func.sum(PositionCampaign.realized_pnl), 0.0).label("sum_pnl"),
    ).filter(
        PositionCampaign.account_id == user_id,
        PositionCampaign.symbol == symbol,
        PositionCampaign.status == "closed",
        PositionCampaign.closed_at.isnot(None),
    )

    # Apply date range filters
    if start_date:
        base_query = base_query.filter(
            func.date(PositionCampaign.closed_at) >= start_date,
        )
    if end_date:
        base_query = base_query.filter(
            func.date(PositionCampaign.closed_at) <= end_date,
        )

    # Group by ISO week and strategy
    results = (
        base_query
        .group_by(
            extract("isoyear", PositionCampaign.closed_at),
            extract("week", PositionCampaign.closed_at),
            PositionCampaign.strategy_id,
        )
        .order_by(
            extract("isoyear", PositionCampaign.closed_at).asc(),
            extract("week", PositionCampaign.closed_at).asc(),
        )
        .all()
    )

    logger.debug("Found %d strategy-week groups for %s", len(results), symbol)

    if not results:
        logger.info("No closed campaigns found for symbol=%s in date range", symbol)
        return StrategyProbeResponse(symbol=symbol, weeks=[])

    # Collect all strategy IDs to fetch names in a single query
    strategy_ids = {r.strategy_id for r in results if r.strategy_id is not None}
    strategy_map: dict[int, Strategy] = {}
    if strategy_ids:
        strategies = db.query(Strategy).filter(Strategy.id.in_(strategy_ids)).all()
        strategy_map = {s.id: s for s in strategies}
        logger.debug("Loaded %d strategies for lookup", len(strategy_map))

    # Group results by (iso_year, iso_week)
    weeks_data: dict[tuple[int, int], list[dict]] = {}
    for row in results:
        iso_year = int(row.iso_year)
        iso_week = int(row.iso_week)
        key = (iso_year, iso_week)

        num_trades = row.num_trades
        sum_pnl = float(row.sum_pnl)
        avg_pnl = sum_pnl / num_trades if num_trades > 0 else 0.0
        weighted_avg_pnl = num_trades * avg_pnl  # same as sum_pnl, per spec

        # Resolve strategy name
        strategy_id = row.strategy_id
        if strategy_id and strategy_id in strategy_map:
            strategy = strategy_map[strategy_id]
            category = strategy.name
            theme = strategy.description or strategy.name
        else:
            category = "untagged"
            theme = "no strategy assigned"

        entry = {
            "category": category,
            "theme": theme,
            "num_trades": num_trades,
            "avg_pnl_per_trade": round(avg_pnl, 2),
            "weighted_avg_pnl": round(weighted_avg_pnl, 2),
        }

        if key not in weeks_data:
            weeks_data[key] = []
        weeks_data[key].append(entry)

    # Build response with ranking within each week
    weeks_response: list[WeekPerformance] = []
    for (iso_year, iso_week), entries in sorted(weeks_data.items()):
        # Sort by weighted_avg_pnl descending
        entries.sort(key=lambda e: e["weighted_avg_pnl"], reverse=True)

        # Assign ranks with tie handling
        ranked_entries: list[StrategyRanking] = []
        current_rank = 1
        for i, entry in enumerate(entries):
            if i > 0 and entry["weighted_avg_pnl"] != entries[i - 1]["weighted_avg_pnl"]:
                current_rank = i + 1

            ranked_entries.append(StrategyRanking(
                category=entry["category"],
                theme=entry["theme"],
                num_trades=entry["num_trades"],
                avg_pnl_per_trade=entry["avg_pnl_per_trade"],
                weighted_avg_pnl=entry["weighted_avg_pnl"],
                rank=current_rank,
            ))

        # Compute week start (Monday) and week end (Sunday) from ISO year/week
        week_start = datetime.strptime(f"{iso_year}-W{iso_week:02d}-1", "%G-W%V-%u").date()
        week_end = datetime.strptime(f"{iso_year}-W{iso_week:02d}-7", "%G-W%V-%u").date()

        weeks_response.append(WeekPerformance(
            week_start=week_start.isoformat(),
            week_end=week_end.isoformat(),
            strategies=ranked_entries,
        ))

    logger.info(
        "Strategy probe complete: symbol=%s, weeks=%d, total_groups=%d",
        symbol, len(weeks_response), len(results),
    )

    return StrategyProbeResponse(symbol=symbol, weeks=weeks_response)
