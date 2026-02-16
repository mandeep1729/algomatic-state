"""Thin helpers to publish reviewer events from API endpoints.

Each function builds an Event with the appropriate EventType and payload,
then publishes it on the message bus. These are fire-and-forget — the
caller does not wait for check completion.
"""

import logging

from src.messaging.bus import get_message_bus
from src.messaging.events import Event, EventType

logger = logging.getLogger(__name__)


def publish_context_updated(
    fill_id: int,
    account_id: int,
) -> None:
    """Publish a REVIEW_CONTEXT_UPDATED event after a DecisionContext is saved.

    Args:
        fill_id: The fill whose context changed
        account_id: Owner's account ID
    """
    bus = get_message_bus()
    bus.publish(Event(
        event_type=EventType.REVIEW_CONTEXT_UPDATED,
        payload={
            "fill_id": fill_id,
            "account_id": account_id,
        },
        source="reviewer.publisher",
    ))
    logger.debug(
        "Published REVIEW_CONTEXT_UPDATED: fill_id=%s account_id=%s",
        fill_id, account_id,
    )


def publish_risk_prefs_updated(account_id: int) -> None:
    """Publish a REVIEW_RISK_PREFS_UPDATED event after risk preferences change.

    Args:
        account_id: The user whose preferences changed
    """
    bus = get_message_bus()
    bus.publish(Event(
        event_type=EventType.REVIEW_RISK_PREFS_UPDATED,
        payload={
            "account_id": account_id,
        },
        source="reviewer.publisher",
    ))
    logger.debug(
        "Published REVIEW_RISK_PREFS_UPDATED: account_id=%s", account_id,
    )


def publish_campaigns_rebuilt(
    account_id: int,
    campaigns_created: int,
) -> None:
    """Publish a REVIEW_CAMPAIGNS_POPULATED event after campaign rebuild.

    Args:
        account_id: The user whose campaigns were rebuilt
        campaigns_created: Number of campaigns created
    """
    if campaigns_created == 0:
        logger.debug(
            "Skipping REVIEW_CAMPAIGNS_POPULATED: no campaigns created for account_id=%s",
            account_id,
        )
        return

    bus = get_message_bus()
    bus.publish(Event(
        event_type=EventType.REVIEW_CAMPAIGNS_POPULATED,
        payload={
            "account_id": account_id,
            "campaigns_created": campaigns_created,
        },
        source="reviewer.publisher",
    ))
    logger.debug(
        "Published REVIEW_CAMPAIGNS_POPULATED: account_id=%s campaigns=%d",
        account_id, campaigns_created,
    )
