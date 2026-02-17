"""ReviewerOrchestrator — subscribes to review events and dispatches checks.

Follows the same lifecycle pattern as MarketDataOrchestrator:
    orchestrator = ReviewerOrchestrator()
    orchestrator.start()   # subscribes to the bus
    ...
    orchestrator.stop()    # unsubscribes

Handles:
- REVIEW_CONTEXT_UPDATED: run checks for a single fill
- REVIEW_RISK_PREFS_UPDATED: re-run checks for recent fills
- REVIEW_CAMPAIGNS_POPULATED: re-run checks after campaign rebuild
- REVIEW_BASELINE_REQUESTED: compute baseline stats for one or all accounts
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.messaging.base import MessageBusBase
from src.messaging.bus import get_message_bus
from src.messaging.events import Event, EventType

logger = logging.getLogger(__name__)


class ReviewerOrchestrator:
    """Listens for reviewer events and dispatches behavioral checks.

    Subscribes to REVIEW_CONTEXT_UPDATED, REVIEW_RISK_PREFS_UPDATED,
    REVIEW_CAMPAIGNS_POPULATED, and REVIEW_BASELINE_REQUESTED events.
    For each event, it opens its own DB session and runs the CheckRunner
    against the relevant decision contexts.

    When api_client is provided, it is passed through to CheckRunner
    for HTTP-based data access and to baseline computation.
    """

    def __init__(
        self,
        message_bus: Optional[MessageBusBase] = None,
        api_client=None,
    ) -> None:
        """Initialize ReviewerOrchestrator.

        Args:
            message_bus: Message bus instance (defaults to global bus)
            api_client: Optional ReviewerApiClient for HTTP-based data access
        """
        self._bus = message_bus or get_message_bus()
        self._api_client = api_client
        self._started = False

    def start(self) -> None:
        """Subscribe to all reviewer events on the message bus."""
        if self._started:
            logger.warning("ReviewerOrchestrator already started")
            return

        self._bus.subscribe(EventType.REVIEW_CONTEXT_UPDATED, self._handle_context_updated)
        self._bus.subscribe(EventType.REVIEW_RISK_PREFS_UPDATED, self._handle_risk_prefs_updated)
        self._bus.subscribe(EventType.REVIEW_CAMPAIGNS_POPULATED, self._handle_campaigns_populated)
        self._bus.subscribe(EventType.REVIEW_BASELINE_REQUESTED, self._handle_baseline_requested)
        self._started = True
        logger.info("ReviewerOrchestrator started")

    def stop(self) -> None:
        """Unsubscribe from the message bus."""
        if not self._started:
            return

        self._bus.unsubscribe(EventType.REVIEW_CONTEXT_UPDATED, self._handle_context_updated)
        self._bus.unsubscribe(EventType.REVIEW_RISK_PREFS_UPDATED, self._handle_risk_prefs_updated)
        self._bus.unsubscribe(EventType.REVIEW_CAMPAIGNS_POPULATED, self._handle_campaigns_populated)
        self._bus.unsubscribe(EventType.REVIEW_BASELINE_REQUESTED, self._handle_baseline_requested)
        self._started = False
        logger.info("ReviewerOrchestrator stopped")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _handle_context_updated(self, event: Event) -> None:
        """Re-run checks after a DecisionContext is saved (strategy assigned)."""
        fill_id = event.payload.get("fill_id")
        if fill_id is None:
            logger.debug(
                "REVIEW_CONTEXT_UPDATED without fill_id, skipping (correlation_id=%s)",
                event.correlation_id,
            )
            return
        logger.info(
            "Handling REVIEW_CONTEXT_UPDATED: fill_id=%s (correlation_id=%s)",
            fill_id, event.correlation_id,
        )
        self._run_checks_for_fill(fill_id, event.correlation_id)

    def _handle_risk_prefs_updated(self, event: Event) -> None:
        """Re-run checks for recent fills when risk preferences change."""
        account_id = event.payload.get("account_id")
        logger.info(
            "Handling REVIEW_RISK_PREFS_UPDATED: account_id=%s (correlation_id=%s)",
            account_id, event.correlation_id,
        )
        self._rerun_checks_for_user(account_id, event.correlation_id)

    def _handle_campaigns_populated(self, event: Event) -> None:
        """Re-run checks for all fills after campaign rebuild."""
        account_id = event.payload.get("account_id")
        logger.info(
            "Handling REVIEW_CAMPAIGNS_POPULATED: account_id=%s (correlation_id=%s)",
            account_id, event.correlation_id,
        )
        self._rerun_checks_for_user(account_id, event.correlation_id)

    def _handle_baseline_requested(self, event: Event) -> None:
        """Compute baseline stats for one or all accounts."""
        account_id = event.payload.get("account_id")
        logger.info(
            "Handling REVIEW_BASELINE_REQUESTED: account_id=%s (correlation_id=%s)",
            account_id, event.correlation_id,
        )

        if self._api_client is None:
            logger.warning(
                "Cannot compute baseline: no API client configured (correlation_id=%s)",
                event.correlation_id,
            )
            return

        from config.settings import get_settings
        from src.reviewer.baseline import compute_baseline_stats

        settings = get_settings()
        lookback_days = settings.checks.baseline_lookback_days
        min_fills = settings.checks.baseline_min_fills

        try:
            if account_id == "all":
                # Batch: compute for all active accounts
                account_ids = self._api_client.get_active_accounts(
                    active_since_days=lookback_days,
                )
                logger.info(
                    "Computing baseline for %d active accounts (correlation_id=%s)",
                    len(account_ids), event.correlation_id,
                )
                for aid in account_ids:
                    try:
                        compute_baseline_stats(
                            aid, self._api_client, lookback_days, min_fills,
                        )
                    except Exception:
                        logger.exception(
                            "Baseline computation failed for account_id=%s", aid,
                        )
            else:
                # Single account
                compute_baseline_stats(
                    int(account_id), self._api_client, lookback_days, min_fills,
                )

        except Exception:
            logger.exception(
                "Failed to handle baseline request (correlation_id=%s)",
                event.correlation_id,
            )

    # ------------------------------------------------------------------
    # Check execution
    # ------------------------------------------------------------------

    def _run_checks_for_fill(self, fill_id: int, correlation_id: str) -> None:
        """Run all behavioral checks for a single fill's decision context."""
        from config.settings import get_settings
        from src.data.database.dependencies import session_scope
        from src.data.database.broker_repository import BrokerRepository
        from src.reviewer.checks.runner import CheckRunner

        settings = get_settings()
        if not settings.reviewer.enabled:
            logger.debug("Reviewer disabled, skipping checks for fill_id=%s", fill_id)
            return

        try:
            with session_scope() as session:
                repo = BrokerRepository(session)

                dc = repo.get_decision_context(fill_id)
                if dc is None:
                    logger.warning(
                        "No DecisionContext for fill_id=%s, skipping checks (correlation_id=%s)",
                        fill_id, correlation_id,
                    )
                    return

                fill = repo.get_fill(fill_id)
                if fill is None:
                    logger.warning(
                        "Fill id=%s not found, skipping checks (correlation_id=%s)",
                        fill_id, correlation_id,
                    )
                    return

                # --- Behavioral checks ---
                runner = CheckRunner(
                    session, settings.checks, api_client=self._api_client,
                )
                checks = runner.run_checks(dc, fill)

                passed = sum(1 for c in checks if c.passed)
                failed = len(checks) - passed

                logger.info(
                    "Checks complete for fill_id=%s: %d passed, %d failed (correlation_id=%s)",
                    fill_id, passed, failed, correlation_id,
                )

                # Publish completion event
                self._bus.publish(Event(
                    event_type=EventType.REVIEW_COMPLETE,
                    payload={
                        "fill_id": fill_id,
                        "check_count": len(checks),
                        "passed": passed,
                        "failed": failed,
                    },
                    source="ReviewerOrchestrator",
                    correlation_id=correlation_id,
                ))

        except Exception:
            logger.exception(
                "Failed to run checks for fill_id=%s (correlation_id=%s)",
                fill_id, correlation_id,
            )
            self._bus.publish(Event(
                event_type=EventType.REVIEW_FAILED,
                payload={
                    "fill_id": fill_id,
                    "error": f"Check execution failed for fill_id={fill_id}",
                },
                source="ReviewerOrchestrator",
                correlation_id=correlation_id,
            ))

    def _rerun_checks_for_user(self, account_id: int, correlation_id: str) -> None:
        """Re-run checks for recent fills belonging to a user."""
        from config.settings import get_settings
        from src.data.database.dependencies import session_scope
        from src.data.database.broker_repository import BrokerRepository

        settings = get_settings()
        if not settings.reviewer.enabled:
            logger.debug("Reviewer disabled, skipping recheck for account_id=%s", account_id)
            return

        lookback_days = settings.reviewer.recheck_lookback_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        try:
            with session_scope() as session:
                repo = BrokerRepository(session)
                fill_id_list = repo.get_recent_fill_ids(account_id, cutoff)

            logger.info(
                "Re-running checks for %d recent fills (account_id=%s, lookback=%d days)",
                len(fill_id_list), account_id, lookback_days,
            )

            for fill_id in fill_id_list:
                self._run_checks_for_fill(fill_id, correlation_id)

        except Exception:
            logger.exception(
                "Failed to rerun checks for account_id=%s (correlation_id=%s)",
                account_id, correlation_id,
            )
