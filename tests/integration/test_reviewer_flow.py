"""Integration tests for the reviewer service event flow.

Tests the end-to-end flow:
  event publish → ReviewerOrchestrator → CheckRunner → result events
"""

from unittest.mock import MagicMock, patch

import pytest

from src.messaging.bus import InMemoryMessageBus
from src.messaging.events import Event, EventType
from src.reviewer.orchestrator import ReviewerOrchestrator


@pytest.fixture
def bus():
    """Fresh in-memory message bus."""
    return InMemoryMessageBus()


def _mock_settings(enabled: bool = True):
    """Create a mock settings object with reviewer config."""
    settings = MagicMock()
    settings.reviewer.enabled = enabled
    settings.checks = MagicMock()
    return settings


def _mock_db_session(leg_id=42, campaign_id=10, account_id=1):
    """Create a mock DB session with a leg query result."""
    mock_session = MagicMock()
    mock_leg = MagicMock()
    mock_leg.id = leg_id
    mock_leg.campaign_id = campaign_id
    mock_leg.campaign.account_id = account_id
    mock_session.query.return_value.filter.return_value.first.return_value = mock_leg

    ctx_manager = MagicMock()
    ctx_manager.__enter__ = MagicMock(return_value=mock_session)
    ctx_manager.__exit__ = MagicMock(return_value=False)
    return ctx_manager


class TestLegCreatedToReviewComplete:
    """Full flow: REVIEW_LEG_CREATED → checks → REVIEW_COMPLETE."""

    @patch("config.settings.get_settings")
    @patch("src.data.database.connection.get_db_manager")
    def test_leg_created_triggers_checks_and_emits_complete(
        self, mock_db_mgr, mock_settings_fn, bus
    ):
        mock_settings_fn.return_value = _mock_settings(enabled=True)
        mock_db_mgr.return_value.get_session.return_value = _mock_db_session(leg_id=42)

        completed_events = []
        bus.subscribe(EventType.REVIEW_COMPLETE, lambda e: completed_events.append(e))

        with patch("src.reviewer.checks.runner.CheckRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            mock_check = MagicMock()
            mock_check.passed = True
            mock_runner.run_checks.return_value = [mock_check]
            mock_runner_cls.return_value = mock_runner

            orch = ReviewerOrchestrator(message_bus=bus)
            orch.start()

            # Publish the trigger event
            bus.publish(Event(
                event_type=EventType.REVIEW_LEG_CREATED,
                payload={"leg_id": 42, "campaign_id": 10, "account_id": 1, "symbol": "AAPL"},
                source="test",
            ))

            orch.stop()

        assert len(completed_events) == 1
        evt = completed_events[0]
        assert evt.payload["leg_id"] == 42
        assert evt.payload["passed"] == 1
        assert evt.payload["failed"] == 0


class TestCampaignsPopulatedFlow:
    """Full flow: REVIEW_CAMPAIGNS_POPULATED → checks for each leg."""

    @patch("config.settings.get_settings")
    @patch("src.data.database.connection.get_db_manager")
    def test_campaigns_populated_runs_checks_for_all_legs(
        self, mock_db_mgr, mock_settings_fn, bus
    ):
        mock_settings_fn.return_value = _mock_settings(enabled=True)
        mock_db_mgr.return_value.get_session.return_value = _mock_db_session()

        completed_events = []
        bus.subscribe(EventType.REVIEW_COMPLETE, lambda e: completed_events.append(e))

        with patch("src.reviewer.checks.runner.CheckRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            mock_check = MagicMock()
            mock_check.passed = True
            mock_runner.run_checks.return_value = [mock_check]
            mock_runner_cls.return_value = mock_runner

            orch = ReviewerOrchestrator(message_bus=bus)
            orch.start()

            bus.publish(Event(
                event_type=EventType.REVIEW_CAMPAIGNS_POPULATED,
                payload={"account_id": 1, "leg_ids": [10, 20, 30]},
                source="test",
            ))

            orch.stop()

        # Should have run checks for each of the 3 legs
        assert len(completed_events) == 3


class TestContextUpdatedFlow:
    """Full flow: REVIEW_CONTEXT_UPDATED → re-run checks."""

    @patch("config.settings.get_settings")
    @patch("src.data.database.connection.get_db_manager")
    def test_context_update_triggers_recheck(
        self, mock_db_mgr, mock_settings_fn, bus
    ):
        mock_settings_fn.return_value = _mock_settings(enabled=True)
        mock_db_mgr.return_value.get_session.return_value = _mock_db_session(leg_id=99)

        completed_events = []
        bus.subscribe(EventType.REVIEW_COMPLETE, lambda e: completed_events.append(e))

        with patch("src.reviewer.checks.runner.CheckRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            mock_runner.run_checks.return_value = []
            mock_runner_cls.return_value = mock_runner

            orch = ReviewerOrchestrator(message_bus=bus)
            orch.start()

            bus.publish(Event(
                event_type=EventType.REVIEW_CONTEXT_UPDATED,
                payload={"leg_id": 99, "campaign_id": 10, "account_id": 1},
                source="test",
            ))

            orch.stop()

        assert len(completed_events) == 1
        assert completed_events[0].payload["leg_id"] == 99

    @patch("config.settings.get_settings")
    @patch("src.data.database.connection.get_db_manager")
    def test_context_update_without_leg_id_is_noop(
        self, mock_db_mgr, mock_settings_fn, bus
    ):
        mock_settings_fn.return_value = _mock_settings(enabled=True)

        completed_events = []
        bus.subscribe(EventType.REVIEW_COMPLETE, lambda e: completed_events.append(e))

        orch = ReviewerOrchestrator(message_bus=bus)
        orch.start()

        bus.publish(Event(
            event_type=EventType.REVIEW_CONTEXT_UPDATED,
            payload={"campaign_id": 10, "account_id": 1},
            source="test",
        ))

        orch.stop()

        assert len(completed_events) == 0


class TestReviewerDisabledFlow:
    """Verify no checks run when reviewer is disabled."""

    @patch("config.settings.get_settings")
    @patch("src.data.database.connection.get_db_manager")
    def test_disabled_reviewer_skips_all_events(
        self, mock_db_mgr, mock_settings_fn, bus
    ):
        mock_settings_fn.return_value = _mock_settings(enabled=False)

        completed_events = []
        failed_events = []
        bus.subscribe(EventType.REVIEW_COMPLETE, lambda e: completed_events.append(e))
        bus.subscribe(EventType.REVIEW_FAILED, lambda e: failed_events.append(e))

        orch = ReviewerOrchestrator(message_bus=bus)
        orch.start()

        bus.publish(Event(
            event_type=EventType.REVIEW_LEG_CREATED,
            payload={"leg_id": 42, "campaign_id": 10, "account_id": 1, "symbol": "AAPL"},
            source="test",
        ))

        orch.stop()

        assert len(completed_events) == 0
        assert len(failed_events) == 0
        mock_db_mgr.return_value.get_session.assert_not_called()


class TestErrorHandlingFlow:
    """Verify error events are published on check failures."""

    @patch("config.settings.get_settings")
    @patch("src.data.database.connection.get_db_manager")
    def test_db_error_publishes_review_failed(
        self, mock_db_mgr, mock_settings_fn, bus
    ):
        mock_settings_fn.return_value = _mock_settings(enabled=True)
        mock_db_mgr.return_value.get_session.side_effect = RuntimeError("DB down")

        failed_events = []
        bus.subscribe(EventType.REVIEW_FAILED, lambda e: failed_events.append(e))

        orch = ReviewerOrchestrator(message_bus=bus)
        orch.start()
        orch._run_checks_for_leg(42, "test-correlation-id")
        orch.stop()

        assert len(failed_events) == 1
        assert failed_events[0].payload["leg_id"] == 42
        assert "error" in failed_events[0].payload
