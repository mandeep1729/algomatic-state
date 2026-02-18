"""CheckRunner — orchestrates behavioral checkers for a trade fill.

Fetches ATR and account balance, runs all registered checkers,
and persists CampaignCheck records linked to the DecisionContext.

Supports two modes:
1. DB-direct mode (original): uses SQLAlchemy session for reads/writes
2. API-client mode (new): uses ReviewerApiClient for data and indicator
   computation, enabling the reviewer service to run as a separate process
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from config.settings import ChecksConfig
from src.reviewer.checks.base import BaseChecker, CheckResult
from src.reviewer.checks.risk_sanity import RiskSanityChecker
from src.reviewer.checks.entry_quality import EntryQualityChecker
from src.data.database.broker_repository import BrokerRepository
from src.data.database.trade_lifecycle_models import (
    CampaignCheck as CampaignCheckModel,
    DecisionContext as DecisionContextModel,
)
from src.data.database.broker_models import TradeFill as TradeFillModel
from src.data.database.trading_buddy_models import (
    UserProfile as UserProfileModel,
)
from src.trade.intent import TradeIntent, TradeDirection, TradeIntentStatus

logger = logging.getLogger(__name__)


class CheckRunner:
    """Runs all registered behavioral checkers against a fill's decision context.

    When an api_client is provided, indicators are fetched via the backend API
    and passed to checkers as kwargs (indicator_snapshot, baseline_stats).
    """

    def __init__(
        self,
        session: Session,
        settings: ChecksConfig,
        api_client=None,
    ):
        """Initialize CheckRunner.

        Args:
            session: SQLAlchemy session for DB reads/writes
            settings: Checks configuration
            api_client: Optional ReviewerApiClient for HTTP-based data access
        """
        self.session = session
        self.settings = settings
        self._api_client = api_client
        self.checkers: list[BaseChecker] = [
            RiskSanityChecker(settings),
            EntryQualityChecker(),
        ]
        self._validate_unique_check_names()

    def _validate_unique_check_names(self) -> None:
        """Ensure all registered checkers have unique CHECK_NAME values."""
        seen: dict[str, str] = {}
        for checker in self.checkers:
            name = checker.CHECK_NAME
            cls_name = checker.__class__.__name__
            if name in seen:
                raise ValueError(
                    f"Duplicate CHECK_NAME '{name}': "
                    f"used by both {seen[name]} and {cls_name}"
                )
            seen[name] = cls_name
        logger.debug(
            "Registered %d checkers: %s",
            len(self.checkers),
            ", ".join(seen.keys()),
        )

    def run_checks(
        self,
        dc: DecisionContextModel,
        fill: TradeFillModel,
    ) -> list[CampaignCheckModel]:
        """Run all checkers for a decision context and persist CampaignCheck records.

        Checkers whose CHECK_NAME already has records for this decision context
        are skipped to avoid redundant evaluations.

        Args:
            dc: The DecisionContext to evaluate
            fill: The linked TradeFill

        Returns:
            List of created CampaignCheck records
        """
        intent = self._build_intent_from_fill(dc, fill)

        # --- Deduplication: find which checkers have already run ---
        existing_check_names = self._get_existing_check_names(dc)
        checkers_to_run = []
        for checker in self.checkers:
            if checker.CHECK_NAME in existing_check_names:
                logger.info(
                    "Skipping checker '%s' for dc_id=%s: already evaluated",
                    checker.CHECK_NAME, dc.id,
                )
            else:
                checkers_to_run.append(checker)
                logger.debug(
                    "Checker '%s' will run for dc_id=%s",
                    checker.CHECK_NAME, dc.id,
                )

        if not checkers_to_run:
            logger.info(
                "All checks already evaluated for fill_id=%s dc_id=%s, nothing to do",
                fill.id, dc.id,
            )
            return []

        # Build kwargs for checkers (indicator snapshot, baseline stats)
        checker_kwargs = {}
        indicator_snapshot = None
        atr = None
        account_balance = None

        if self._api_client:
            # API-client mode: fetch indicators and profile via HTTP
            indicator_snapshot = self._fetch_indicator_snapshot_via_api(fill)
            if indicator_snapshot:
                atr = indicator_snapshot.get("atr_14")
                checker_kwargs["indicator_snapshot"] = indicator_snapshot

            profile_data = self._get_profile_via_api(dc.account_id)
            if profile_data:
                account_balance = profile_data.get("account_balance")
                baseline_stats = profile_data.get("stats")
                if baseline_stats:
                    checker_kwargs["baseline_stats"] = baseline_stats
        else:
            # DB-direct mode (legacy)
            atr = self._fetch_atr(fill)
            account_balance = self._get_account_balance(dc.account_id)

        logger.info(
            "Running %d/%d checks for fill_id=%s dc_id=%s: atr=%s balance=%s has_snapshot=%s",
            len(checkers_to_run), len(self.checkers),
            fill.id, dc.id, atr, account_balance, indicator_snapshot is not None,
        )

        all_results: list[CheckResult] = []
        for checker in checkers_to_run:
            try:
                results = checker.run(
                    fill, intent, atr, account_balance, **checker_kwargs,
                )
                all_results.extend(results)
            except Exception:
                logger.exception(
                    "Checker '%s' failed for fill_id=%s",
                    checker.CHECK_NAME, fill.id,
                )

        # Persist as CampaignCheck records linked to decision_context
        checks: list[CampaignCheckModel] = []
        for result in all_results:
            check = CampaignCheckModel(
                decision_context_id=dc.id,
                account_id=dc.account_id,
                check_type=result.check_type,
                check_name=result.code,
                severity=result.severity,
                passed=result.passed,
                details=result.details,
                nudge_text=result.nudge_text,
                check_phase=result.check_phase,
                checked_at=datetime.utcnow(),
            )
            self.session.add(check)
            checks.append(check)

        self.session.flush()
        logger.info(
            "Persisted %d check records for fill_id=%s dc_id=%s",
            len(checks), fill.id, dc.id,
        )

        # Write entry quality results to inferred_context via API
        if self._api_client:
            self._save_entry_quality_to_inferred_context(fill.id, all_results)

        return checks

    def _get_existing_check_names(
        self, dc: DecisionContextModel,
    ) -> set[str]:
        """Query previously-recorded check names for a decision context.

        Uses BrokerRepository to look up which checker CHECK_NAMEs already
        have CampaignCheck records for this (account_id, decision_context_id).

        Returns an empty set if the query fails (fail-open: run all checks).
        """
        try:
            repo = BrokerRepository(self.session)
            return repo.get_existing_check_names(dc.account_id, dc.id)
        except Exception:
            logger.debug(
                "Could not query existing checks for dc_id=%s, will run all",
                dc.id, exc_info=True,
            )
            return set()

    # ------------------------------------------------------------------
    # Intent building
    # ------------------------------------------------------------------

    def _build_intent_from_fill(
        self,
        dc: DecisionContextModel,
        fill: TradeFillModel,
    ) -> Optional[TradeIntent]:
        """Build a TradeIntent domain object from fill data.

        Since intents are no longer persisted, we construct a minimal
        TradeIntent from the fill's trade data for checkers that need it.

        Returns None if the fill doesn't have enough data for an intent.
        """
        try:
            direction = TradeDirection.LONG if fill.side.lower() == "buy" else TradeDirection.SHORT

            # Extract stop/target from exit_intent if available
            stop_loss = fill.price
            profit_target = fill.price
            if dc.exit_intent and isinstance(dc.exit_intent, dict):
                stop_loss = dc.exit_intent.get("stop_loss", fill.price) or fill.price
                profit_target = dc.exit_intent.get("profit_target", fill.price) or fill.price

            return TradeIntent(
                user_id=dc.account_id,
                account_id=dc.account_id,
                symbol=fill.symbol,
                direction=direction,
                timeframe="1Day",  # Default — fills don't carry timeframe
                entry_price=fill.price,
                stop_loss=float(stop_loss),
                profit_target=float(profit_target),
                position_size=fill.quantity,
                position_value=fill.quantity * fill.price,
                status=TradeIntentStatus.EVALUATED,
            )
        except Exception:
            logger.debug(
                "Could not build intent from fill_id=%s", fill.id, exc_info=True,
            )
            return None

    # ------------------------------------------------------------------
    # API-client data fetching
    # ------------------------------------------------------------------

    def _fetch_indicator_snapshot_via_api(
        self, fill: TradeFillModel,
    ) -> Optional[dict]:
        """Fetch OHLCV bars via API and compute indicator snapshot locally.

        Args:
            fill: TradeFill to compute indicators for

        Returns:
            Dict of indicator values at the fill bar, or None
        """
        try:
            # Determine timeframe from decision context
            dc = fill.decision_context
            timeframe = "15Min"
            if dc and dc.exit_intent and isinstance(dc.exit_intent, dict):
                timeframe = dc.exit_intent.get("timeframe", "15Min") or "15Min"

            executed_at = fill.executed_at.isoformat() if fill.executed_at else None
            if not executed_at:
                return None

            bars = self._api_client.get_ohlcv_bars(
                symbol=fill.symbol,
                timeframe=timeframe,
                end=executed_at,
                last_n_bars=250,
            )

            if not bars or len(bars) < 30:
                logger.debug(
                    "Insufficient bars for %s/%s at %s (%d bars)",
                    fill.symbol, timeframe, executed_at, len(bars) if bars else 0,
                )
                return None

            # Convert to DataFrame and compute indicators
            from src.reviewer.baseline import _bars_to_dataframe, _compute_indicator_snapshot
            df = _bars_to_dataframe(bars)
            return _compute_indicator_snapshot(df)

        except Exception:
            logger.debug(
                "Failed to fetch indicator snapshot for fill_id=%s",
                fill.id, exc_info=True,
            )
            return None

    def _get_profile_via_api(self, account_id: int) -> Optional[dict]:
        """Fetch user profile via API client.

        Returns:
            Profile dict with account_balance, stats, etc. or None
        """
        try:
            return self._api_client.get_profile(account_id)
        except Exception:
            logger.debug(
                "Could not fetch profile via API for account_id=%s",
                account_id, exc_info=True,
            )
            return None

    # ------------------------------------------------------------------
    # Entry quality → inferred_context
    # ------------------------------------------------------------------

    def _save_entry_quality_to_inferred_context(
        self, fill_id: int, results: list[CheckResult],
    ) -> None:
        """Extract EQ000 composite result and save to inferred_context via API."""
        eq_result = next(
            (r for r in results if r.code == "EQ000"), None,
        )
        if eq_result is None:
            return

        try:
            self._api_client.save_inferred_context(
                fill_id,
                {"entry_quality": eq_result.details},
            )
        except Exception:
            logger.debug(
                "Failed to save entry quality inferred context for fill_id=%s",
                fill_id, exc_info=True,
            )

    # ------------------------------------------------------------------
    # Legacy DB-direct data fetching
    # ------------------------------------------------------------------

    def _fetch_atr(self, fill: TradeFillModel) -> Optional[float]:
        """Fetch the ATR value for this fill's symbol.

        Uses the atr_14 column from the features table.
        Returns None if unavailable.
        """
        try:
            from src.data.database.models import FeatureRow

            row = self.session.query(FeatureRow).filter(
                FeatureRow.symbol == fill.symbol,
            ).order_by(FeatureRow.timestamp.desc()).first()

            if row is None:
                logger.debug("No feature row found for symbol=%s", fill.symbol)
                return None

            atr_value = getattr(row, "atr_14", None)
            if atr_value is not None:
                logger.debug(
                    "Fetched atr_14=%.4f for symbol=%s", atr_value, fill.symbol,
                )
            return atr_value

        except Exception:
            logger.debug(
                "Could not fetch ATR for fill_id=%s: feature table may not exist",
                fill.id, exc_info=True,
            )
            return None

    def _get_account_balance(self, account_id: int) -> Optional[float]:
        """Get the account balance for a user."""
        try:
            profile = self.session.query(UserProfileModel).filter(
                UserProfileModel.user_account_id == account_id,
            ).first()

            if profile is None:
                logger.debug("No profile found for account_id=%s", account_id)
                return None

            balance = profile.account_balance
            logger.debug(
                "Account balance=%.2f for account_id=%s",
                balance or 0, account_id,
            )
            return balance

        except Exception:
            logger.debug(
                "Could not fetch account balance for account_id=%s",
                account_id, exc_info=True,
            )
            return None
