"""Thin helpers to publish reviewer events from API endpoints.

Each function builds an Event with the appropriate EventType and payload,
then publishes it on the message bus. These are fire-and-forget — the
caller does not wait for check completion.
"""

import logging

from src.messaging.bus import get_message_bus
from src.messaging.events import Event, EventType

logger = logging.getLogger(__name__)


def publish_leg_created(
    leg_id: int,
    campaign_id: int,
    account_id: int,
    symbol: str,
) -> None:
    """Publish a REVIEW_LEG_CREATED event after a new campaign leg is created.

    Args:
        leg_id: The newly created leg's ID
        campaign_id: Parent campaign ID
        account_id: Owner's account ID
        symbol: Ticker symbol for the campaign
    """
    bus = get_message_bus()
    bus.publish(Event(
        event_type=EventType.REVIEW_LEG_CREATED,
        payload={
            "leg_id": leg_id,
            "campaign_id": campaign_id,
            "account_id": account_id,
            "symbol": symbol,
        },
        source="reviewer.publisher",
    ))
    logger.debug(
        "Published REVIEW_LEG_CREATED: leg_id=%s campaign_id=%s",
        leg_id, campaign_id,
    )


def publish_context_updated(
    leg_id: int,
    campaign_id: int,
    account_id: int,
) -> None:
    """Publish a REVIEW_CONTEXT_UPDATED event after a DecisionContext is saved.

    Args:
        leg_id: The leg whose context changed
        campaign_id: Parent campaign ID
        account_id: Owner's account ID
    """
    bus = get_message_bus()
    bus.publish(Event(
        event_type=EventType.REVIEW_CONTEXT_UPDATED,
        payload={
            "leg_id": leg_id,
            "campaign_id": campaign_id,
            "account_id": account_id,
        },
        source="reviewer.publisher",
    ))
    logger.debug(
        "Published REVIEW_CONTEXT_UPDATED: leg_id=%s campaign_id=%s",
        leg_id, campaign_id,
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


def publish_campaigns_populated(
    account_id: int,
    leg_ids: list[int],
) -> None:
    """Publish a REVIEW_CAMPAIGNS_POPULATED event after batch campaign population.

    Args:
        account_id: The user whose campaigns were populated
        leg_ids: IDs of all legs created during population
    """
    if not leg_ids:
        logger.debug(
            "Skipping REVIEW_CAMPAIGNS_POPULATED: no legs created for account_id=%s",
            account_id,
        )
        return

    bus = get_message_bus()
    bus.publish(Event(
        event_type=EventType.REVIEW_CAMPAIGNS_POPULATED,
        payload={
            "account_id": account_id,
            "leg_ids": leg_ids,
        },
        source="reviewer.publisher",
    ))
    logger.debug(
        "Published REVIEW_CAMPAIGNS_POPULATED: account_id=%s leg_count=%d",
        account_id, len(leg_ids),
    )
