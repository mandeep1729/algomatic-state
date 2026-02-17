"""Repository for strategy probe data access.

Centralizes complex aggregation queries previously in src/api/strategy_probe.py.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import case, extract, func
from sqlalchemy.orm import Session

from src.data.database.probe_models import ProbeStrategy, StrategyProbeResult

logger = logging.getLogger(__name__)


class ProbeRepository:
    """Repository for strategy probe queries and aggregations."""

    def __init__(self, session: Session):
        self.session = session

    def list_strategies_by_type(
        self,
        strategy_type: str,
        active_only: bool = True,
    ) -> list[ProbeStrategy]:
        """Get probe strategies by strategy_type (theme)."""
        query = self.session.query(ProbeStrategy).filter(
            ProbeStrategy.strategy_type == strategy_type,
        )
        if active_only:
            query = query.filter(ProbeStrategy.is_active == True)  # noqa: E712
        return query.order_by(ProbeStrategy.display_name.asc()).all()

    def get_available_timeframes(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        direction: Optional[str] = None,
    ) -> list[str]:
        """Get distinct timeframes with probe results for a symbol."""
        query = self.session.query(StrategyProbeResult.timeframe).filter(
            StrategyProbeResult.symbol == symbol.upper(),
        )
        if start_date:
            query = query.filter(StrategyProbeResult.open_day >= start_date)
        if end_date:
            query = query.filter(StrategyProbeResult.open_day <= end_date)
        if direction:
            query = query.filter(StrategyProbeResult.long_short == direction)

        return sorted(row.timeframe for row in query.distinct().all())

    def get_weekly_theme_rankings(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        timeframe: Optional[str] = None,
        direction: Optional[str] = None,
    ) -> list[dict]:
        """Get theme rankings grouped by ISO week.

        Returns list of dicts with keys:
            iso_year, iso_week, theme, total_trades, profitable_trades,
            unprofitable_trades, long_trades, short_trades, sum_pnl.
        """
        symbol = symbol.upper()

        query = self.session.query(
            extract("isoyear", StrategyProbeResult.open_day).label("iso_year"),
            extract("week", StrategyProbeResult.open_day).label("iso_week"),
            ProbeStrategy.strategy_type.label("theme"),
            func.sum(StrategyProbeResult.num_trades).label("total_trades"),
            func.sum(
                case(
                    (StrategyProbeResult.pnl_mean > 0, StrategyProbeResult.num_trades),
                    else_=0,
                )
            ).label("profitable_trades"),
            func.sum(
                case(
                    (StrategyProbeResult.pnl_mean <= 0, StrategyProbeResult.num_trades),
                    else_=0,
                )
            ).label("unprofitable_trades"),
            func.sum(
                case(
                    (StrategyProbeResult.long_short == "long", StrategyProbeResult.num_trades),
                    else_=0,
                )
            ).label("long_trades"),
            func.sum(
                case(
                    (StrategyProbeResult.long_short == "short", StrategyProbeResult.num_trades),
                    else_=0,
                )
            ).label("short_trades"),
            func.sum(
                StrategyProbeResult.num_trades * StrategyProbeResult.pnl_mean,
            ).label("sum_pnl"),
        ).join(
            ProbeStrategy, StrategyProbeResult.strategy_id == ProbeStrategy.id,
        ).filter(
            StrategyProbeResult.symbol == symbol,
        )

        if start_date:
            query = query.filter(StrategyProbeResult.open_day >= start_date)
        if end_date:
            query = query.filter(StrategyProbeResult.open_day <= end_date)
        if timeframe:
            query = query.filter(StrategyProbeResult.timeframe == timeframe)
        if direction:
            query = query.filter(StrategyProbeResult.long_short == direction)

        rows = (
            query.group_by(
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

        return [
            {
                "iso_year": int(row.iso_year),
                "iso_week": int(row.iso_week),
                "theme": row.theme,
                "total_trades": int(row.total_trades),
                "profitable_trades": int(row.profitable_trades),
                "unprofitable_trades": int(row.unprofitable_trades),
                "long_trades": int(row.long_trades),
                "short_trades": int(row.short_trades),
                "sum_pnl": float(row.sum_pnl),
            }
            for row in rows
        ]

    def get_top_strategy_names_by_week(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        timeframe: Optional[str] = None,
        direction: Optional[str] = None,
    ) -> dict[tuple[int, int, str], str]:
        """Get best strategy display_name per (iso_year, iso_week, theme).

        Ranks individual strategies by PnL within each (week, theme) group.

        Returns:
            Dict mapping (iso_year, iso_week, theme) -> display_name.
        """
        symbol = symbol.upper()

        query = self.session.query(
            extract("isoyear", StrategyProbeResult.open_day).label("iso_year"),
            extract("week", StrategyProbeResult.open_day).label("iso_week"),
            ProbeStrategy.strategy_type.label("theme"),
            ProbeStrategy.display_name,
            func.sum(
                StrategyProbeResult.num_trades * StrategyProbeResult.pnl_mean,
            ).label("strat_pnl"),
        ).join(
            ProbeStrategy, StrategyProbeResult.strategy_id == ProbeStrategy.id,
        ).filter(
            StrategyProbeResult.symbol == symbol,
        )

        if start_date:
            query = query.filter(StrategyProbeResult.open_day >= start_date)
        if end_date:
            query = query.filter(StrategyProbeResult.open_day <= end_date)
        if timeframe:
            query = query.filter(StrategyProbeResult.timeframe == timeframe)
        if direction:
            query = query.filter(StrategyProbeResult.long_short == direction)

        rows = (
            query.group_by(
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

        result: dict[tuple[int, int, str], str] = {}
        for row in rows:
            key = (int(row.iso_year), int(row.iso_week), row.theme or "unknown")
            if key not in result:
                result[key] = row.display_name
        return result

    def get_top_strategies(
        self,
        symbol: str,
        strategy_type: str,
        week_start: date,
        week_end: date,
        timeframe: Optional[str] = None,
        limit: int = 3,
    ) -> list[dict]:
        """Get top strategies for a theme within a specific week.

        Returns list of dicts with keys:
            id, display_name, name, philosophy, direction, details,
            total_trades, sum_pnl, profitable_trades, unprofitable_trades.
        """
        symbol = symbol.upper()

        query = self.session.query(
            ProbeStrategy.id,
            ProbeStrategy.display_name,
            ProbeStrategy.name,
            ProbeStrategy.philosophy,
            ProbeStrategy.direction,
            ProbeStrategy.details,
            func.sum(StrategyProbeResult.num_trades).label("total_trades"),
            func.sum(
                StrategyProbeResult.num_trades * StrategyProbeResult.pnl_mean,
            ).label("sum_pnl"),
            func.sum(
                case(
                    (StrategyProbeResult.pnl_mean > 0, StrategyProbeResult.num_trades),
                    else_=0,
                )
            ).label("profitable_trades"),
            func.sum(
                case(
                    (StrategyProbeResult.pnl_mean <= 0, StrategyProbeResult.num_trades),
                    else_=0,
                )
            ).label("unprofitable_trades"),
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
            query.group_by(
                ProbeStrategy.id,
                ProbeStrategy.display_name,
                ProbeStrategy.name,
                ProbeStrategy.philosophy,
                ProbeStrategy.direction,
                ProbeStrategy.details,
            )
            .order_by(
                func.sum(StrategyProbeResult.num_trades * StrategyProbeResult.pnl_mean).desc(),
            )
            .limit(limit)
            .all()
        )

        return [
            {
                "id": row.id,
                "display_name": row.display_name,
                "name": row.name,
                "philosophy": row.philosophy,
                "direction": row.direction,
                "details": row.details or {},
                "total_trades": int(row.total_trades),
                "sum_pnl": float(row.sum_pnl),
                "profitable_trades": int(row.profitable_trades),
                "unprofitable_trades": int(row.unprofitable_trades),
            }
            for row in rows
        ]

    def get_best_theme(
        self,
        ticker: str,
        timeframe: str,
        lookback_days: int = 3,
        asof_date: Optional[date] = None,
    ) -> Optional[str]:
        """Get the best-performing strategy theme for a ticker and timeframe.

        Groups by strategy_type and ranks by weighted PnL.

        Args:
            ticker: Ticker symbol.
            timeframe: Timeframe string.
            lookback_days: Days to look back from asof_date.
            asof_date: Reference date (defaults to today).

        Returns:
            Best theme name or None.
        """
        ticker = ticker.upper()
        if asof_date is None:
            asof_date = date.today()
        start_date = asof_date - timedelta(days=lookback_days)

        rows = self.session.query(
            ProbeStrategy.strategy_type.label("theme"),
            func.sum(StrategyProbeResult.num_trades).label("total_trades"),
            func.sum(
                StrategyProbeResult.num_trades * StrategyProbeResult.pnl_mean,
            ).label("sum_pnl"),
        ).join(
            StrategyProbeResult, StrategyProbeResult.strategy_id == ProbeStrategy.id,
        ).filter(
            StrategyProbeResult.symbol == ticker,
            StrategyProbeResult.timeframe == timeframe,
            StrategyProbeResult.open_day >= start_date,
            StrategyProbeResult.open_day <= asof_date,
        ).group_by(
            ProbeStrategy.strategy_type,
        ).order_by(
            func.sum(StrategyProbeResult.num_trades * StrategyProbeResult.pnl_mean).desc(),
            func.sum(StrategyProbeResult.num_trades).desc(),
        ).all()

        if not rows:
            logger.info(
                "No theme data for ticker=%s, timeframe=%s, lookback from %s",
                ticker, timeframe, asof_date,
            )
            return None

        best = rows[0]
        logger.info(
            "Best theme: %s (pnl=%.2f, trades=%d) for ticker=%s, timeframe=%s",
            best.theme, best.sum_pnl, best.total_trades, ticker, timeframe,
        )
        return best.theme
