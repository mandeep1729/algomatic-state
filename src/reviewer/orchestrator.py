"""ReviewerOrchestrator — subscribes to review events and dispatches checks.

Follows the same lifecycle pattern as MarketDataOrchestrator:
    orchestrator = ReviewerOrchestrator()
    orchestrator.start()   # subscribes to the bus
    ...
    orchestrator.stop()    # unsubscribes
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

    Subscribes to REVIEW_LEG_CREATED, REVIEW_CONTEXT_UPDATED,
    REVIEW_RISK_PREFS_UPDATED, and REVIEW_CAMPAIGNS_POPULATED events.
    For each event, it opens its own DB session via get_db_manager().get_session()
    and runs the CheckRunner against the relevant legs.
    """

    def __init__(self, message_bus: Optional[MessageBusBase] = None) -> None:
        self._bus = message_bus or get_message_bus()
        self._started = False

    def start(self) -> None:
        """Subscribe to all reviewer events on the message bus."""
        if self._started:
            logger.warning("ReviewerOrchestrator already started")
            return

        self._bus.subscribe(EventType.REVIEW_LEG_CREATED, self._handle_leg_created)
        self._bus.subscribe(EventType.REVIEW_CONTEXT_UPDATED, self._handle_context_updated)
        self._bus.subscribe(EventType.REVIEW_RISK_PREFS_UPDATED, self._handle_risk_prefs_updated)
        self._bus.subscribe(EventType.REVIEW_CAMPAIGNS_POPULATED, self._handle_campaigns_populated)
        self._started = True
        logger.info("ReviewerOrchestrator started")

    def stop(self) -> None:
        """Unsubscribe from the message bus."""
        if not self._started:
            return

        self._bus.unsubscribe(EventType.REVIEW_LEG_CREATED, self._handle_leg_created)
        self._bus.unsubscribe(EventType.REVIEW_CONTEXT_UPDATED, self._handle_context_updated)
        self._bus.unsubscribe(EventType.REVIEW_RISK_PREFS_UPDATED, self._handle_risk_prefs_updated)
        self._bus.unsubscribe(EventType.REVIEW_CAMPAIGNS_POPULATED, self._handle_campaigns_populated)
        self._started = False
        logger.info("ReviewerOrchestrator stopped")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _handle_leg_created(self, event: Event) -> None:
        """Run checks for a newly created campaign leg."""
        leg_id = event.payload.get("leg_id")
        logger.info(
            "Handling REVIEW_LEG_CREATED: leg_id=%s (correlation_id=%s)",
            leg_id, event.correlation_id,
        )
        self._run_checks_for_leg(leg_id, event.correlation_id)

    def _handle_context_updated(self, event: Event) -> None:
        """Re-run checks after a DecisionContext is saved (strategy assigned)."""
        leg_id = event.payload.get("leg_id")
        if leg_id is None:
            logger.debug(
                "REVIEW_CONTEXT_UPDATED without leg_id, skipping (correlation_id=%s)",
                event.correlation_id,
            )
            return
        logger.info(
            "Handling REVIEW_CONTEXT_UPDATED: leg_id=%s (correlation_id=%s)",
            leg_id, event.correlation_id,
        )
        self._run_checks_for_leg(leg_id, event.correlation_id)

    def _handle_risk_prefs_updated(self, event: Event) -> None:
        """Re-run checks for recent legs when risk preferences change."""
        account_id = event.payload.get("account_id")
        logger.info(
            "Handling REVIEW_RISK_PREFS_UPDATED: account_id=%s (correlation_id=%s)",
            account_id, event.correlation_id,
        )
        self._rerun_checks_for_user(account_id, event.correlation_id)

    def _handle_campaigns_populated(self, event: Event) -> None:
        """Run checks for all legs created during batch population."""
        leg_ids = event.payload.get("leg_ids", [])
        account_id = event.payload.get("account_id")
        logger.info(
            "Handling REVIEW_CAMPAIGNS_POPULATED: account_id=%s, %d legs (correlation_id=%s)",
            account_id, len(leg_ids), event.correlation_id,
        )
        for leg_id in leg_ids:
            self._run_checks_for_leg(leg_id, event.correlation_id)

    # ------------------------------------------------------------------
    # Check execution
    # ------------------------------------------------------------------

    def _run_checks_for_leg(self, leg_id: int, correlation_id: str) -> None:
        """Run all behavioral checks for a single leg in its own DB session."""
        from config.settings import get_settings
        from src.data.database.connection import get_db_manager
        from src.data.database.trade_lifecycle_models import CampaignLeg as CampaignLegModel
        from src.reviewer.checks.runner import CheckRunner

        settings = get_settings()
        if not settings.reviewer.enabled:
            logger.debug("Reviewer disabled, skipping checks for leg_id=%s", leg_id)
            return

        try:
            with get_db_manager().get_session() as session:
                leg = session.query(CampaignLegModel).filter(
                    CampaignLegModel.id == leg_id
                ).first()

                if leg is None:
                    logger.warning(
                        "Leg id=%s not found, skipping checks (correlation_id=%s)",
                        leg_id, correlation_id,
                    )
                    return

                runner = CheckRunner(session, settings.checks)
                checks = runner.run_checks(leg)

                passed = sum(1 for c in checks if c.passed)
                failed = len(checks) - passed

                logger.info(
                    "Checks complete for leg_id=%s: %d passed, %d failed (correlation_id=%s)",
                    leg_id, passed, failed, correlation_id,
                )

                # Publish completion event
                self._bus.publish(Event(
                    event_type=EventType.REVIEW_COMPLETE,
                    payload={
                        "leg_id": leg_id,
                        "check_count": len(checks),
                        "passed": passed,
                        "failed": failed,
                    },
                    source="ReviewerOrchestrator",
                    correlation_id=correlation_id,
                ))

        except Exception:
            logger.exception(
                "Failed to run checks for leg_id=%s (correlation_id=%s)",
                leg_id, correlation_id,
            )
            self._bus.publish(Event(
                event_type=EventType.REVIEW_FAILED,
                payload={
                    "leg_id": leg_id,
                    "error": f"Check execution failed for leg_id={leg_id}",
                },
                source="ReviewerOrchestrator",
                correlation_id=correlation_id,
            ))

    def _rerun_checks_for_user(self, account_id: int, correlation_id: str) -> None:
        """Re-run checks for recent legs belonging to a user.

        Queries CampaignLeg joined to PositionCampaign where account_id
        matches and started_at >= now - recheck_lookback_days.
        """
        from config.settings import get_settings
        from src.data.database.connection import get_db_manager
        from src.data.database.trade_lifecycle_models import (
            CampaignLeg as CampaignLegModel,
            PositionCampaign as PositionCampaignModel,
        )

        settings = get_settings()
        if not settings.reviewer.enabled:
            logger.debug("Reviewer disabled, skipping recheck for account_id=%s", account_id)
            return

        lookback_days = settings.reviewer.recheck_lookback_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        try:
            with get_db_manager().get_session() as session:
                leg_ids = (
                    session.query(CampaignLegModel.id)
                    .join(
                        PositionCampaignModel,
                        PositionCampaignModel.id == CampaignLegModel.campaign_id,
                    )
                    .filter(
                        PositionCampaignModel.account_id == account_id,
                        CampaignLegModel.started_at >= cutoff,
                    )
                    .all()
                )

            leg_id_list = [row[0] for row in leg_ids]
            logger.info(
                "Re-running checks for %d recent legs (account_id=%s, lookback=%d days)",
                len(leg_id_list), account_id, lookback_days,
            )

            for leg_id in leg_id_list:
                self._run_checks_for_leg(leg_id, correlation_id)

        except Exception:
            logger.exception(
                "Failed to rerun checks for account_id=%s (correlation_id=%s)",
                account_id, correlation_id,
            )
