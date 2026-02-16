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


class TestPublishContextUpdated:
    """Tests for publish_context_updated."""

    def test_publishes_event(self, mock_bus):
        from src.reviewer.publisher import publish_context_updated

        publish_context_updated(fill_id=1, account_id=100)

        mock_bus.publish.assert_called_once()
        event = mock_bus.publish.call_args[0][0]
        assert event.event_type == EventType.REVIEW_CONTEXT_UPDATED
        assert event.payload == {
            "fill_id": 1,
            "account_id": 100,
        }
        assert event.source == "reviewer.publisher"


class TestPublishRiskPrefsUpdated:
    """Tests for publish_risk_prefs_updated."""

    def test_publishes_event(self, mock_bus):
        from src.reviewer.publisher import publish_risk_prefs_updated

        publish_risk_prefs_updated(account_id=100)

        mock_bus.publish.assert_called_once()
        event = mock_bus.publish.call_args[0][0]
        assert event.event_type == EventType.REVIEW_RISK_PREFS_UPDATED
        assert event.payload == {"account_id": 100}


class TestPublishCampaignsRebuilt:
    """Tests for publish_campaigns_rebuilt."""

    def test_publishes_event(self, mock_bus):
        from src.reviewer.publisher import publish_campaigns_rebuilt

        publish_campaigns_rebuilt(account_id=100, campaigns_created=3)

        mock_bus.publish.assert_called_once()
        event = mock_bus.publish.call_args[0][0]
        assert event.event_type == EventType.REVIEW_CAMPAIGNS_POPULATED
        assert event.payload == {
            "account_id": 100,
            "campaigns_created": 3,
        }

    def test_skips_zero_campaigns(self, mock_bus):
        from src.reviewer.publisher import publish_campaigns_rebuilt

        publish_campaigns_rebuilt(account_id=100, campaigns_created=0)

        mock_bus.publish.assert_not_called()
