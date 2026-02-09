"""ProbeRunner orchestrator for running strategies across symbols/timeframes/risk profiles."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

from src.data.database.connection import get_db_manager
from src.data.database.market_repository import OHLCVRepository
from src.data.database.probe_models import StrategyProbeResult
from src.data.database.probe_repository import ProbeRepository
from src.data.timeframe_aggregator import TimeframeAggregator, INTRADAY_AGGREGATABLE
from src.features.talib_indicators import TALibIndicatorCalculator
from src.strats_prob.aggregator import aggregate_trades
from src.strats_prob.engine import ProbeEngine
from src.strats_prob.exits import RISK_PROFILES
from src.strats_prob.registry import get_all_strategies, get_strategy
from src.strats_prob.strategy_def import ProbeTradeResult, StrategyDef

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
    persist_trades: bool = False  # Default: do not persist individual trades

    def __post_init__(self):
        if self.run_id is None:
            self.run_id = str(uuid.uuid4())[:8]
        logger.info(
            "ProbeRunConfig: symbols=%s, persist_trades=%s, run_id=%s",
            self.symbols, self.persist_trades, self.run_id,
        )


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

        all_required: set[str] = set()
        for strat in strategies:
            all_required.update(strat.required_indicators)

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

        # Pre-populate missing timeframes before running strategies
        self._ensure_timeframes_populated()

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

                df = self._ensure_indicators(df, symbol, timeframe, all_required)

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

                                # Persist individual trade records if configured
                                if self.config.persist_trades:
                                    self._store_trades(
                                        trades=trades,
                                        run_id=run_id,
                                        strategy_id=strategy_db_id,
                                        symbol=symbol,
                                        timeframe=timeframe,
                                        risk_profile=risk_name,
                                    )

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

    def _ensure_timeframes_populated(self) -> None:
        """Aggregate missing higher-timeframe bars before running strategies.

        For each symbol in the config, calls TimeframeAggregator to fill any
        missing intraday timeframes (e.g. 15Min, 1Hour from 1Min data).
        Only processes timeframes that are both requested in the config AND
        aggregatable from 1Min data.

        This step is non-fatal: aggregation failures are logged as warnings
        and the probe run continues with whatever data already exists.
        """
        aggregatable = [
            tf for tf in self.config.timeframes
            if tf in INTRADAY_AGGREGATABLE
        ]
        if not aggregatable:
            logger.debug(
                "No aggregatable timeframes in config (%s), skipping pre-population",
                self.config.timeframes,
            )
            return

        aggregator = TimeframeAggregator(db_manager=self.db_manager)

        for symbol in self.config.symbols:
            try:
                summary = aggregator.aggregate_missing_timeframes(
                    ticker=symbol,
                    target_timeframes=aggregatable,
                )
                logger.info(
                    "Ensured timeframes %s populated for %s: %s",
                    aggregatable, symbol, summary,
                )
            except Exception:
                logger.warning(
                    "Timeframe aggregation failed for %s — continuing with existing data",
                    symbol,
                    exc_info=True,
                )

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

    def _ensure_indicators(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        required_indicators: set[str],
    ) -> pd.DataFrame:
        """Compute missing indicators if any required columns are absent.

        Checks required_indicators against df.columns. If all present, returns
        immediately. Otherwise, runs TALibIndicatorCalculator.compute() on the
        OHLCV data, merges new columns into df, and persists features to DB
        for future runs.

        Args:
            df: Combined OHLCV + features DataFrame.
            symbol: Ticker symbol.
            timeframe: Bar timeframe string.
            required_indicators: Union of all strategy required_indicators.

        Returns:
            DataFrame with indicator columns added (if any were missing).
        """
        if not required_indicators:
            return df

        missing = required_indicators - set(df.columns)
        if not missing:
            logger.debug(
                "All %d required indicators present for %s/%s",
                len(required_indicators), symbol, timeframe,
            )
            return df

        logger.warning(
            "Missing %d indicators for %s/%s: %s — computing via TALib",
            len(missing), symbol, timeframe, sorted(missing),
        )

        ohlcv_cols = ["open", "high", "low", "close", "volume"]
        ohlcv_df = df[ohlcv_cols]

        calculator = TALibIndicatorCalculator()
        features_df = calculator.compute(ohlcv_df)

        # Merge only NEW columns to avoid overwriting existing features
        new_cols = [c for c in features_df.columns if c not in df.columns]
        if new_cols:
            df = df.join(features_df[new_cols])
            logger.info(
                "Added %d computed indicator columns for %s/%s",
                len(new_cols), symbol, timeframe,
            )

        still_missing = required_indicators - set(df.columns)
        if still_missing:
            logger.warning(
                "%d indicators still missing after computation for %s/%s: %s",
                len(still_missing), symbol, timeframe, sorted(still_missing),
            )

        # Persist to DB for future runs (non-fatal if it fails)
        self._save_features_to_db(features_df, symbol, timeframe)

        return df

    def _save_features_to_db(
        self,
        features_df: pd.DataFrame,
        symbol: str,
        timeframe: str,
    ) -> None:
        """Persist computed features to the database for future runs.

        Uses OHLCVRepository.store_features() to upsert feature JSONB rows.
        Failures are logged but do not interrupt the probe run.

        Args:
            features_df: DataFrame of computed indicator columns.
            symbol: Ticker symbol.
            timeframe: Bar timeframe string.
        """
        try:
            with self.db_manager.get_session() as session:
                repo = OHLCVRepository(session)
                ticker = repo.get_ticker(symbol)
                if ticker is None:
                    logger.warning(
                        "Ticker %s not found in DB, skipping feature persistence",
                        symbol,
                    )
                    return

                count = repo.store_features(features_df, ticker.id, timeframe)
                logger.info(
                    "Persisted %d feature rows for %s/%s to database",
                    count, symbol, timeframe,
                )
        except Exception:
            logger.exception(
                "Failed to persist features for %s/%s — continuing with in-memory data",
                symbol, timeframe,
            )

    def _store_results(self, records: list[dict]) -> None:
        """Store aggregated results in the database."""
        with self.db_manager.get_session() as session:
            repo = ProbeRepository(session)
            repo.bulk_insert_results(records)

    def _store_trades(
        self,
        trades: list[ProbeTradeResult],
        run_id: str,
        strategy_id: int,
        symbol: str,
        timeframe: str,
        risk_profile: str,
    ) -> None:
        """Store individual trade records linked to their aggregated result rows.

        Looks up the StrategyProbeResult rows for the given dimensions, then maps
        each trade to the correct result row based on (open_day, open_hour, long_short).
        Failures are logged but do not interrupt the probe run.

        Args:
            trades: List of ProbeTradeResult from the engine.
            run_id: Run identifier.
            strategy_id: FK to probe_strategies.
            symbol: Ticker symbol.
            timeframe: Bar timeframe string.
            risk_profile: Risk profile name.
        """
        try:
            with self.db_manager.get_session() as session:
                # Query all result rows for this combination to get their IDs
                result_rows = session.query(StrategyProbeResult).filter(
                    StrategyProbeResult.run_id == run_id,
                    StrategyProbeResult.strategy_id == strategy_id,
                    StrategyProbeResult.symbol == symbol.upper(),
                    StrategyProbeResult.timeframe == timeframe,
                    StrategyProbeResult.risk_profile == risk_profile,
                ).all()

                if not result_rows:
                    logger.warning(
                        "No result rows found for trade persistence "
                        "(run=%s, strategy=%d, %s/%s/%s)",
                        run_id, strategy_id, symbol, timeframe, risk_profile,
                    )
                    return

                # Build lookup: (open_day, open_hour, long_short) -> result_id
                result_id_map: dict[tuple, int] = {}
                for row in result_rows:
                    key = (row.open_day, row.open_hour, row.long_short)
                    result_id_map[key] = row.id

                # Map trades to result rows
                trade_dicts = []
                for trade in trades:
                    open_day = trade.entry_time.date()
                    open_hour = trade.entry_time.hour
                    direction = trade.direction[:5]
                    key = (open_day, open_hour, direction)

                    result_id = result_id_map.get(key)
                    if result_id is None:
                        logger.debug(
                            "No result row for trade group key %s, skipping trade",
                            key,
                        )
                        continue

                    pnl_currency = trade.pnl_pct * trade.entry_price

                    trade_dicts.append({
                        "strategy_probe_result_id": result_id,
                        "ticker": symbol.upper(),
                        "open_timestamp": trade.entry_time,
                        "close_timestamp": trade.exit_time,
                        "direction": direction,
                        "open_justification": trade.entry_justification,
                        "close_justification": trade.exit_justification,
                        "pnl": pnl_currency,
                        "pnl_pct": trade.pnl_pct,
                        "bars_held": trade.bars_held,
                        "max_drawdown": trade.max_drawdown_pct,
                        "max_profit": trade.max_profit_pct,
                        "pnl_std": trade.pnl_std,
                    })

                if trade_dicts:
                    repo = ProbeRepository(session)
                    repo.bulk_insert_trades(trade_dicts)
                    logger.info(
                        "Persisted %d trade records for %s/%s/%s/%s",
                        len(trade_dicts), symbol, timeframe, risk_profile,
                        run_id,
                    )

        except Exception:
            logger.exception(
                "Failed to persist trades for %s/%s/%s — continuing",
                symbol, timeframe, risk_profile,
            )
