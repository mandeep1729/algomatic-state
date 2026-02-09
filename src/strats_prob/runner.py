"""ProbeRunner orchestrator for running strategies across symbols/timeframes/risk profiles."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

from src.data.database.connection import get_db_manager
from src.data.database.market_repository import OHLCVRepository
from src.data.database.probe_repository import ProbeRepository
from src.strats_prob.aggregator import aggregate_trades
from src.strats_prob.engine import ProbeEngine
from src.strats_prob.exits import RISK_PROFILES
from src.strats_prob.registry import get_all_strategies, get_strategy
from src.strats_prob.strategy_def import StrategyDef

logger = logging.getLogger(__name__)


@dataclass
class ProbeRunConfig:
    """Configuration for a probe run."""

    symbols: list[str]
    timeframes: list[str] = field(default_factory=lambda: ["1Min", "15Min", "1Hour", "1Day"])
    risk_profiles: list[str] = field(default_factory=lambda: ["low", "medium", "high"])
    strategy_ids: Optional[list[int]] = None  # None = all strategies
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    run_id: Optional[str] = None

    def __post_init__(self):
        if self.run_id is None:
            self.run_id = str(uuid.uuid4())[:8]


class ProbeRunner:
    """Orchestrate strategy probes across all combinations.

    For each (symbol, timeframe), loads data ONCE from the database,
    then runs all selected strategies with all risk profiles against it.
    """

    def __init__(self, config: ProbeRunConfig):
        self.config = config
        self.db_manager = get_db_manager()

    def run(self) -> str:
        """Execute the probe run.

        Returns:
            The run_id string.
        """
        run_id = self.config.run_id
        strategies = self._get_strategies()
        total_combos = (
            len(self.config.symbols)
            * len(self.config.timeframes)
            * len(strategies)
            * len(self.config.risk_profiles)
        )

        logger.info(
            "Starting probe run %s: %d symbols x %d timeframes x %d strategies x %d risk_profiles = %d combinations",
            run_id,
            len(self.config.symbols),
            len(self.config.timeframes),
            len(strategies),
            len(self.config.risk_profiles),
            total_combos,
        )

        combo_count = 0
        total_trades = 0
        total_records = 0

        for symbol in self.config.symbols:
            for timeframe in self.config.timeframes:
                # Load data ONCE per (symbol, timeframe)
                df = self._load_data(symbol, timeframe)
                if df is None or df.empty:
                    logger.warning("No data for %s/%s, skipping", symbol, timeframe)
                    continue

                logger.info(
                    "Loaded %d bars for %s/%s (%s to %s)",
                    len(df), symbol, timeframe,
                    df.index.min(), df.index.max(),
                )

                for strat in strategies:
                    for risk_name in self.config.risk_profiles:
                        combo_count += 1
                        risk_profile = RISK_PROFILES[risk_name]

                        try:
                            engine = ProbeEngine(strat, risk_profile)
                            trades = engine.run(df)

                            if trades:
                                # Get strategy DB ID
                                strategy_db_id = self._get_strategy_db_id(strat)
                                if strategy_db_id is None:
                                    logger.warning(
                                        "Strategy %s not found in DB, skipping aggregation",
                                        strat.name,
                                    )
                                    continue

                                records = aggregate_trades(
                                    trades=trades,
                                    strategy_id=strategy_db_id,
                                    symbol=symbol,
                                    timeframe=timeframe,
                                    risk_profile=risk_name,
                                    run_id=run_id,
                                    period_start=self.config.start or df.index.min(),
                                    period_end=self.config.end or df.index.max(),
                                )

                                if records:
                                    self._store_results(records)
                                    total_records += len(records)

                                total_trades += len(trades)

                        except Exception:
                            logger.exception(
                                "Error running strategy %s (%s/%s/%s)",
                                strat.name, symbol, timeframe, risk_name,
                            )

                        if combo_count % 50 == 0:
                            logger.info(
                                "Progress: %d/%d combinations (%d trades, %d records)",
                                combo_count, total_combos, total_trades, total_records,
                            )

        logger.info(
            "Probe run %s complete: %d combinations, %d trades, %d records stored",
            run_id, combo_count, total_trades, total_records,
        )
        return run_id

    def _get_strategies(self) -> list[StrategyDef]:
        """Get strategies to run based on config."""
        if self.config.strategy_ids:
            strategies = []
            for sid in self.config.strategy_ids:
                s = get_strategy(sid)
                if s:
                    strategies.append(s)
                else:
                    logger.warning("Strategy ID %d not found in registry", sid)
            return strategies
        return get_all_strategies()

    def _load_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Load OHLCV bars and merge with pre-computed features."""
        with self.db_manager.get_session() as session:
            repo = OHLCVRepository(session)

            # Load OHLCV bars
            ohlcv_df = repo.get_bars(
                symbol=symbol,
                timeframe=timeframe,
                start=self.config.start,
                end=self.config.end,
            )
            if ohlcv_df.empty:
                return None

            # Load pre-computed features
            features_df = repo.get_features(
                symbol=symbol,
                timeframe=timeframe,
                start=self.config.start,
                end=self.config.end,
            )

            if features_df.empty:
                logger.warning(
                    "No features for %s/%s, running with OHLCV only",
                    symbol, timeframe,
                )
                return ohlcv_df

            # Merge on datetime index
            combined = ohlcv_df.join(features_df, how="inner")
            logger.debug(
                "Combined %d bars + %d feature columns for %s/%s",
                len(combined), len(features_df.columns), symbol, timeframe,
            )
            return combined

    def _get_strategy_db_id(self, strat: StrategyDef) -> Optional[int]:
        """Look up the strategy's DB primary key."""
        with self.db_manager.get_session() as session:
            repo = ProbeRepository(session)
            db_strat = repo.get_strategy_by_name(strat.name)
            return db_strat.id if db_strat else None

    def _store_results(self, records: list[dict]) -> None:
        """Store aggregated results in the database."""
        with self.db_manager.get_session() as session:
            repo = ProbeRepository(session)
            repo.bulk_insert_results(records)
