"""Unit tests for ReviewerOrchestrator event handling."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from src.messaging.bus import InMemoryMessageBus
from src.messaging.events import Event, EventType
from src.reviewer.orchestrator import ReviewerOrchestrator


@pytest.fixture
def bus():
    """Fresh in-memory message bus."""
    return InMemoryMessageBus()


@pytest.fixture
def orchestrator(bus):
    """ReviewerOrchestrator wired to the test bus."""
    orch = ReviewerOrchestrator(message_bus=bus)
    orch.start()
    yield orch
    orch.stop()


class TestLifecycle:
    """Tests for start/stop lifecycle."""

    def test_start_subscribes(self, bus):
        orch = ReviewerOrchestrator(message_bus=bus)
        orch.start()
        assert orch._started is True
        orch.stop()

    def test_double_start_is_noop(self, bus):
        orch = ReviewerOrchestrator(message_bus=bus)
        orch.start()
        orch.start()  # should not raise
        assert orch._started is True
        orch.stop()

    def test_stop_unsubscribes(self, bus):
        orch = ReviewerOrchestrator(message_bus=bus)
        orch.start()
        orch.stop()
        assert orch._started is False

    def test_stop_without_start_is_noop(self, bus):
        orch = ReviewerOrchestrator(message_bus=bus)
        orch.stop()  # should not raise


class TestContextUpdatedHandler:
    """Tests for REVIEW_CONTEXT_UPDATED event handling."""

    @patch.object(ReviewerOrchestrator, "_run_checks_for_fill")
    def test_dispatches_to_run_checks(self, mock_run, orchestrator, bus):
        event = Event(
            event_type=EventType.REVIEW_CONTEXT_UPDATED,
            payload={"fill_id": 42, "account_id": 1},
            source="test",
        )
        bus.publish(event)

        mock_run.assert_called_once_with(42, event.correlation_id)

    @patch.object(ReviewerOrchestrator, "_run_checks_for_fill")
    def test_skips_when_no_fill_id(self, mock_run, orchestrator, bus):
        event = Event(
            event_type=EventType.REVIEW_CONTEXT_UPDATED,
            payload={"account_id": 1},
            source="test",
        )
        bus.publish(event)

        mock_run.assert_not_called()


class TestRiskPrefsUpdatedHandler:
    """Tests for REVIEW_RISK_PREFS_UPDATED event handling."""

    @patch.object(ReviewerOrchestrator, "_rerun_checks_for_user")
    def test_dispatches_to_rerun_checks(self, mock_rerun, orchestrator, bus):
        event = Event(
            event_type=EventType.REVIEW_RISK_PREFS_UPDATED,
            payload={"account_id": 100},
            source="test",
        )
        bus.publish(event)

        mock_rerun.assert_called_once_with(100, event.correlation_id)


class TestCampaignsPopulatedHandler:
    """Tests for REVIEW_CAMPAIGNS_POPULATED event handling."""

    @patch.object(ReviewerOrchestrator, "_rerun_checks_for_user")
    def test_dispatches_to_rerun_checks(self, mock_rerun, orchestrator, bus):
        event = Event(
            event_type=EventType.REVIEW_CAMPAIGNS_POPULATED,
            payload={"account_id": 100, "campaigns_created": 3},
            source="test",
        )
        bus.publish(event)

        mock_rerun.assert_called_once_with(100, event.correlation_id)


class TestRunChecksForFill:
    """Tests for _run_checks_for_fill with mocked DB."""

    @patch("config.settings.get_settings")
    @patch("src.data.database.dependencies.session_scope")
    def test_publishes_review_complete_on_success(self, mock_session_scope, mock_settings, bus):
        """Verify REVIEW_COMPLETE event is published after successful checks."""
        # Setup settings mock
        settings = MagicMock()
        settings.reviewer.enabled = True
        settings.checks = MagicMock()
        mock_settings.return_value = settings

        # Setup DB mock via session_scope context manager
        mock_session = MagicMock()

        # Mock DecisionContext query
        mock_dc = MagicMock()
        mock_dc.id = 10
        mock_dc.account_id = 1

        # Mock TradeFill query
        mock_fill = MagicMock()
        mock_fill.id = 42

        # First .filter().first() returns dc, second returns fill
        mock_session.query.return_value.filter.return_value.first.side_effect = [
            mock_dc,  # DecisionContext query
            mock_fill,  # TradeFill query
        ]

        @contextmanager
        def _mock_scope():
            yield mock_session

        mock_session_scope.side_effect = _mock_scope

        # Mock CheckRunner
        with patch("src.reviewer.checks.runner.CheckRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            mock_check = MagicMock()
            mock_check.passed = True
            mock_runner.run_checks.return_value = [mock_check]
            mock_runner_cls.return_value = mock_runner

            # Track published events
            events_published = []
            bus.subscribe(EventType.REVIEW_COMPLETE, lambda e: events_published.append(e))

            orch = ReviewerOrchestrator(message_bus=bus)
            orch.start()
            orch._run_checks_for_fill(42, "test-corr-id")
            orch.stop()

            assert len(events_published) == 1
            evt = events_published[0]
            assert evt.payload["fill_id"] == 42
            assert evt.payload["passed"] == 1
            assert evt.payload["failed"] == 0

    @patch("config.settings.get_settings")
    @patch("src.data.database.dependencies.session_scope")
    def test_skips_when_disabled(self, mock_session_scope, mock_settings, bus):
        """Reviewer checks are skipped when reviewer.enabled=False."""
        settings = MagicMock()
        settings.reviewer.enabled = False
        mock_settings.return_value = settings

        orch = ReviewerOrchestrator(message_bus=bus)
        orch.start()
        orch._run_checks_for_fill(42, "test-corr-id")
        orch.stop()

        mock_session_scope.assert_not_called()

    @patch("config.settings.get_settings")
    @patch("src.data.database.dependencies.session_scope")
    def test_publishes_review_failed_on_error(self, mock_session_scope, mock_settings, bus):
        """REVIEW_FAILED event is published when checks raise."""
        settings = MagicMock()
        settings.reviewer.enabled = True
        mock_settings.return_value = settings

        mock_session_scope.side_effect = RuntimeError("DB down")

        events_published = []
        bus.subscribe(EventType.REVIEW_FAILED, lambda e: events_published.append(e))

        orch = ReviewerOrchestrator(message_bus=bus)
        orch.start()
        orch._run_checks_for_fill(42, "test-corr-id")
        orch.stop()

        assert len(events_published) == 1
        assert events_published[0].payload["fill_id"] == 42
        assert "failed" in events_published[0].payload["error"].lower()
