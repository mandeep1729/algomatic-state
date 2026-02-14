"""Unit tests for reviewer publisher functions."""

from unittest.mock import MagicMock, patch

import pytest

from src.messaging.events import EventType


@pytest.fixture
def mock_bus():
    """Mock message bus."""
    bus = MagicMock()
    with patch("src.reviewer.publisher.get_message_bus", return_value=bus):
        yield bus


class TestPublishLegCreated:
    """Tests for publish_leg_created."""

    def test_publishes_event(self, mock_bus):
        from src.reviewer.publisher import publish_leg_created

        publish_leg_created(leg_id=1, campaign_id=10, account_id=100, symbol="AAPL")

        mock_bus.publish.assert_called_once()
        event = mock_bus.publish.call_args[0][0]
        assert event.event_type == EventType.REVIEW_LEG_CREATED
        assert event.payload == {
            "leg_id": 1,
            "campaign_id": 10,
            "account_id": 100,
            "symbol": "AAPL",
        }
        assert event.source == "reviewer.publisher"


class TestPublishContextUpdated:
    """Tests for publish_context_updated."""

    def test_publishes_event(self, mock_bus):
        from src.reviewer.publisher import publish_context_updated

        publish_context_updated(leg_id=1, campaign_id=10, account_id=100)

        mock_bus.publish.assert_called_once()
        event = mock_bus.publish.call_args[0][0]
        assert event.event_type == EventType.REVIEW_CONTEXT_UPDATED
        assert event.payload == {
            "leg_id": 1,
            "campaign_id": 10,
            "account_id": 100,
        }


class TestPublishRiskPrefsUpdated:
    """Tests for publish_risk_prefs_updated."""

    def test_publishes_event(self, mock_bus):
        from src.reviewer.publisher import publish_risk_prefs_updated

        publish_risk_prefs_updated(account_id=100)

        mock_bus.publish.assert_called_once()
        event = mock_bus.publish.call_args[0][0]
        assert event.event_type == EventType.REVIEW_RISK_PREFS_UPDATED
        assert event.payload == {"account_id": 100}


class TestPublishCampaignsPopulated:
    """Tests for publish_campaigns_populated."""

    def test_publishes_event(self, mock_bus):
        from src.reviewer.publisher import publish_campaigns_populated

        publish_campaigns_populated(account_id=100, leg_ids=[1, 2, 3])

        mock_bus.publish.assert_called_once()
        event = mock_bus.publish.call_args[0][0]
        assert event.event_type == EventType.REVIEW_CAMPAIGNS_POPULATED
        assert event.payload == {
            "account_id": 100,
            "leg_ids": [1, 2, 3],
        }

    def test_skips_empty_leg_ids(self, mock_bus):
        from src.reviewer.publisher import publish_campaigns_populated

        publish_campaigns_populated(account_id=100, leg_ids=[])

        mock_bus.publish.assert_not_called()
