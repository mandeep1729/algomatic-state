"""Data access layer for strategy probe system."""

import logging
from typing import Optional

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.data.database.probe_models import ProbeStrategy, ProbeStrategyTrade, StrategyProbeResult

logger = logging.getLogger(__name__)


class ProbeRepository:
    """Repository for probe strategy catalog and results.

    Follows the same session-based pattern as OHLCVRepository.
    """

    def __init__(self, session: Session):
        self.session = session

    # -------------------------------------------------------------------------
    # Strategy catalog operations
    # -------------------------------------------------------------------------

    def get_or_create_strategy(
        self,
        name: str,
        display_name: str,
        philosophy: str,
        strategy_type: str,
        direction: str,
        details: dict,
    ) -> ProbeStrategy:
        """Get existing strategy by name or create a new one.

        Args:
            name: Machine-readable name (e.g. "ema20_ema50_trend_cross")
            display_name: Human-readable name
            philosophy: Brief rationale
            strategy_type: Category (trend, mean_reversion, etc.)
            direction: long_short, long_only, or short_only
            details: JSONB with entry/exit rules, tags, indicators

        Returns:
            ProbeStrategy instance
        """
        strategy = self.get_strategy_by_name(name)
        if strategy is None:
            strategy = ProbeStrategy(
                name=name,
                display_name=display_name,
                philosophy=philosophy,
                strategy_type=strategy_type,
                direction=direction,
                details=details,
            )
            self.session.add(strategy)
            self.session.flush()
            logger.info("Created probe strategy: %s", name)
        return strategy

    def get_strategy_by_name(self, name: str) -> Optional[ProbeStrategy]:
        """Look up strategy by machine-readable name."""
        return self.session.query(ProbeStrategy).filter(
            ProbeStrategy.name == name,
        ).first()

    def get_strategy_by_id(self, strategy_id: int) -> Optional[ProbeStrategy]:
        """Look up strategy by primary key."""
        return self.session.query(ProbeStrategy).get(strategy_id)

    def list_strategies(self, strategy_type: Optional[str] = None) -> list[ProbeStrategy]:
        """List all strategies, optionally filtered by type."""
        query = self.session.query(ProbeStrategy).filter(ProbeStrategy.is_active == True)
        if strategy_type:
            query = query.filter(ProbeStrategy.strategy_type == strategy_type)
        return query.order_by(ProbeStrategy.id).all()

    def seed_strategies(self, strategies: list[dict]) -> int:
        """Bulk upsert strategies by name.

        Args:
            strategies: List of dicts with keys matching ProbeStrategy columns.

        Returns:
            Number of rows affected.
        """
        if not strategies:
            return 0

        stmt = pg_insert(ProbeStrategy).values(strategies)
        stmt = stmt.on_conflict_do_update(
            index_elements=["name"],
            set_={
                "display_name": stmt.excluded.display_name,
                "philosophy": stmt.excluded.philosophy,
                "strategy_type": stmt.excluded.strategy_type,
                "direction": stmt.excluded.direction,
                "details": stmt.excluded.details,
                "is_active": True,
            },
        )
        result = self.session.execute(stmt)
        logger.info("Seeded %d probe strategies", result.rowcount)
        return result.rowcount

    # -------------------------------------------------------------------------
    # Probe result operations
    # -------------------------------------------------------------------------

    def bulk_insert_results(self, records: list[dict]) -> int:
        """Bulk insert probe result records with ON CONFLICT DO NOTHING.

        Args:
            records: List of dicts matching StrategyProbeResult columns.

        Returns:
            Number of rows inserted.
        """
        if not records:
            return 0

        stmt = pg_insert(StrategyProbeResult).values(records)
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_probe_result_dimensions",
        )
        result = self.session.execute(stmt)
        logger.info("Inserted %d probe result records", result.rowcount)
        return result.rowcount

    def get_results(
        self,
        symbol: Optional[str] = None,
        strategy_id: Optional[int] = None,
        timeframe: Optional[str] = None,
        risk_profile: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> pd.DataFrame:
        """Query probe results with optional filters, returned as DataFrame.

        Args:
            symbol: Filter by symbol
            strategy_id: Filter by strategy FK
            timeframe: Filter by timeframe
            risk_profile: Filter by risk profile
            run_id: Filter by run identifier

        Returns:
            DataFrame with probe result rows.
        """
        query = self.session.query(StrategyProbeResult)

        if symbol:
            query = query.filter(StrategyProbeResult.symbol == symbol.upper())
        if strategy_id is not None:
            query = query.filter(StrategyProbeResult.strategy_id == strategy_id)
        if timeframe:
            query = query.filter(StrategyProbeResult.timeframe == timeframe)
        if risk_profile:
            query = query.filter(StrategyProbeResult.risk_profile == risk_profile)
        if run_id:
            query = query.filter(StrategyProbeResult.run_id == run_id)

        query = query.order_by(StrategyProbeResult.id)
        results = query.all()

        if not results:
            return pd.DataFrame()

        rows = []
        for r in results:
            rows.append({
                "id": r.id,
                "run_id": r.run_id,
                "symbol": r.symbol,
                "strategy_id": r.strategy_id,
                "timeframe": r.timeframe,
                "risk_profile": r.risk_profile,
                "open_day": r.open_day,
                "open_hour": r.open_hour,
                "long_short": r.long_short,
                "num_trades": r.num_trades,
                "pnl_mean": r.pnl_mean,
                "pnl_std": r.pnl_std,
                "max_drawdown": r.max_drawdown,
                "max_profit": r.max_profit,
                "period_start": r.period_start,
                "period_end": r.period_end,
            })
        return pd.DataFrame(rows)

    def delete_run(self, run_id: str) -> int:
        """Delete all results for a given run_id.

        Cascading deletes will also remove associated trade records.

        Args:
            run_id: Run identifier.

        Returns:
            Number of rows deleted.
        """
        count = self.session.query(StrategyProbeResult).filter(
            StrategyProbeResult.run_id == run_id,
        ).delete(synchronize_session=False)
        logger.info("Deleted %d probe results for run_id=%s", count, run_id)
        return count

    # -------------------------------------------------------------------------
    # Trade-level operations
    # -------------------------------------------------------------------------

    def bulk_insert_trades(self, trades: list[dict]) -> int:
        """Bulk insert individual trade records.

        Args:
            trades: List of dicts matching ProbeStrategyTrade columns.
                    Each dict must include strategy_probe_result_id, ticker,
                    open_timestamp, close_timestamp, direction, pnl, pnl_pct,
                    and bars_held. open_justification and close_justification
                    are optional.

        Returns:
            Number of rows inserted.
        """
        if not trades:
            return 0

        self.session.bulk_insert_mappings(ProbeStrategyTrade, trades)
        self.session.flush()
        logger.info("Inserted %d probe trade records", len(trades))
        return len(trades)

    def get_trades(
        self,
        result_id: Optional[int] = None,
        ticker: Optional[str] = None,
        direction: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> pd.DataFrame:
        """Query individual trade records with optional filters.

        Args:
            result_id: Filter by strategy_probe_result_id FK.
            ticker: Filter by ticker symbol.
            direction: Filter by direction (long/short).
            run_id: Filter by run_id via join to strategy_probe_results.

        Returns:
            DataFrame with trade rows.
        """
        query = self.session.query(ProbeStrategyTrade)

        if result_id is not None:
            query = query.filter(ProbeStrategyTrade.strategy_probe_result_id == result_id)
        if ticker:
            query = query.filter(ProbeStrategyTrade.ticker == ticker.upper())
        if direction:
            query = query.filter(ProbeStrategyTrade.direction == direction)
        if run_id:
            query = query.join(StrategyProbeResult).filter(
                StrategyProbeResult.run_id == run_id,
            )

        query = query.order_by(ProbeStrategyTrade.open_timestamp)
        results = query.all()

        if not results:
            return pd.DataFrame()

        rows = []
        for t in results:
            rows.append({
                "id": t.id,
                "strategy_probe_result_id": t.strategy_probe_result_id,
                "ticker": t.ticker,
                "open_timestamp": t.open_timestamp,
                "close_timestamp": t.close_timestamp,
                "direction": t.direction,
                "open_justification": t.open_justification,
                "close_justification": t.close_justification,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct,
                "bars_held": t.bars_held,
            })
        return pd.DataFrame(rows)
