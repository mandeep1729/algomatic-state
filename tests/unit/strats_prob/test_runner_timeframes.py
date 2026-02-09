"""Unit tests for ProbeRunner timeframe pre-population logic."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from src.strats_prob.runner import ProbeRunConfig, ProbeRunner


class TestEnsureTimeframesPopulated:
    """Tests for ProbeRunner._ensure_timeframes_populated()."""

    @patch("src.strats_prob.runner.get_db_manager")
    def _make_runner(self, timeframes, mock_get_db):
        """Helper to build a ProbeRunner with a mocked DB manager."""
        mock_get_db.return_value = MagicMock()
        config = ProbeRunConfig(
            symbols=["AAPL", "SPY"],
            timeframes=timeframes,
        )
        runner = ProbeRunner(config)
        return runner

    @patch("src.strats_prob.runner.get_db_manager")
    @patch("src.strats_prob.runner.TimeframeAggregator")
    def test_aggregates_intraday_timeframes(self, mock_agg_cls, mock_get_db, caplog):
        """Aggregator is called for each symbol with only aggregatable timeframes."""
        mock_get_db.return_value = MagicMock()
        mock_agg_instance = MagicMock()
        mock_agg_instance.aggregate_missing_timeframes.return_value = {
            "15Min": 100,
            "1Hour": 25,
        }
        mock_agg_cls.return_value = mock_agg_instance

        config = ProbeRunConfig(
            symbols=["AAPL", "SPY"],
            timeframes=["1Min", "15Min", "1Hour", "1Day"],
        )
        runner = ProbeRunner(config)

        with caplog.at_level(logging.INFO, logger="src.strats_prob.runner"):
            runner._ensure_timeframes_populated()

        # Aggregator should be constructed once with the runner's db_manager
        mock_agg_cls.assert_called_once_with(db_manager=runner.db_manager)

        # Called once per symbol, with only the aggregatable timeframes
        assert mock_agg_instance.aggregate_missing_timeframes.call_count == 2

        calls = mock_agg_instance.aggregate_missing_timeframes.call_args_list
        assert calls[0].kwargs == {
            "ticker": "AAPL",
            "target_timeframes": ["15Min", "1Hour"],
        }
        assert calls[1].kwargs == {
            "ticker": "SPY",
            "target_timeframes": ["15Min", "1Hour"],
        }

        # Verify logging
        assert "Ensured timeframes" in caplog.text
        assert "AAPL" in caplog.text
        assert "SPY" in caplog.text

    @patch("src.strats_prob.runner.get_db_manager")
    @patch("src.strats_prob.runner.TimeframeAggregator")
    def test_skips_when_only_1min_requested(self, mock_agg_cls, mock_get_db, caplog):
        """No aggregation when only 1Min is in timeframes."""
        mock_get_db.return_value = MagicMock()
        config = ProbeRunConfig(
            symbols=["AAPL"],
            timeframes=["1Min"],
        )
        runner = ProbeRunner(config)

        with caplog.at_level(logging.DEBUG, logger="src.strats_prob.runner"):
            runner._ensure_timeframes_populated()

        mock_agg_cls.assert_not_called()
        assert "skipping pre-population" in caplog.text

    @patch("src.strats_prob.runner.get_db_manager")
    @patch("src.strats_prob.runner.TimeframeAggregator")
    def test_skips_when_only_1day_requested(self, mock_agg_cls, mock_get_db, caplog):
        """No aggregation when only 1Day is in timeframes (not intraday aggregatable)."""
        mock_get_db.return_value = MagicMock()
        config = ProbeRunConfig(
            symbols=["AAPL"],
            timeframes=["1Day"],
        )
        runner = ProbeRunner(config)

        with caplog.at_level(logging.DEBUG, logger="src.strats_prob.runner"):
            runner._ensure_timeframes_populated()

        mock_agg_cls.assert_not_called()
        assert "skipping pre-population" in caplog.text

    @patch("src.strats_prob.runner.get_db_manager")
    @patch("src.strats_prob.runner.TimeframeAggregator")
    def test_skips_when_1min_and_1day_only(self, mock_agg_cls, mock_get_db, caplog):
        """No aggregation when timeframes are only 1Min and 1Day."""
        mock_get_db.return_value = MagicMock()
        config = ProbeRunConfig(
            symbols=["AAPL"],
            timeframes=["1Min", "1Day"],
        )
        runner = ProbeRunner(config)

        with caplog.at_level(logging.DEBUG, logger="src.strats_prob.runner"):
            runner._ensure_timeframes_populated()

        mock_agg_cls.assert_not_called()

    @patch("src.strats_prob.runner.get_db_manager")
    @patch("src.strats_prob.runner.TimeframeAggregator")
    def test_aggregation_failure_is_non_fatal(self, mock_agg_cls, mock_get_db, caplog):
        """Aggregation errors are caught and logged, run continues."""
        mock_get_db.return_value = MagicMock()
        mock_agg_instance = MagicMock()
        mock_agg_instance.aggregate_missing_timeframes.side_effect = RuntimeError(
            "DB connection failed"
        )
        mock_agg_cls.return_value = mock_agg_instance

        config = ProbeRunConfig(
            symbols=["AAPL"],
            timeframes=["15Min"],
        )
        runner = ProbeRunner(config)

        with caplog.at_level(logging.WARNING, logger="src.strats_prob.runner"):
            # Should NOT raise
            runner._ensure_timeframes_populated()

        assert "Timeframe aggregation failed for AAPL" in caplog.text
        assert "continuing with existing data" in caplog.text

    @patch("src.strats_prob.runner.get_db_manager")
    @patch("src.strats_prob.runner.TimeframeAggregator")
    def test_partial_failure_continues_for_other_symbols(
        self, mock_agg_cls, mock_get_db, caplog
    ):
        """If aggregation fails for one symbol, it continues for the next."""
        mock_get_db.return_value = MagicMock()
        mock_agg_instance = MagicMock()

        # First call (AAPL) fails, second call (SPY) succeeds
        mock_agg_instance.aggregate_missing_timeframes.side_effect = [
            RuntimeError("AAPL failed"),
            {"15Min": 50},
        ]
        mock_agg_cls.return_value = mock_agg_instance

        config = ProbeRunConfig(
            symbols=["AAPL", "SPY"],
            timeframes=["15Min"],
        )
        runner = ProbeRunner(config)

        with caplog.at_level(logging.INFO, logger="src.strats_prob.runner"):
            runner._ensure_timeframes_populated()

        # Both symbols should have been attempted
        assert mock_agg_instance.aggregate_missing_timeframes.call_count == 2
        assert "Timeframe aggregation failed for AAPL" in caplog.text
        assert "Ensured timeframes" in caplog.text
        assert "SPY" in caplog.text

    @patch("src.strats_prob.runner.get_db_manager")
    @patch("src.strats_prob.runner.TimeframeAggregator")
    def test_filters_to_only_15min(self, mock_agg_cls, mock_get_db):
        """When only 15Min is aggregatable, only 15Min is passed."""
        mock_get_db.return_value = MagicMock()
        mock_agg_instance = MagicMock()
        mock_agg_instance.aggregate_missing_timeframes.return_value = {"15Min": 10}
        mock_agg_cls.return_value = mock_agg_instance

        config = ProbeRunConfig(
            symbols=["AAPL"],
            timeframes=["1Min", "15Min", "1Day"],
        )
        runner = ProbeRunner(config)
        runner._ensure_timeframes_populated()

        call_kwargs = mock_agg_instance.aggregate_missing_timeframes.call_args.kwargs
        assert call_kwargs["target_timeframes"] == ["15Min"]

    @patch("src.strats_prob.runner.get_db_manager")
    @patch("src.strats_prob.runner.TimeframeAggregator")
    def test_filters_to_only_1hour(self, mock_agg_cls, mock_get_db):
        """When only 1Hour is aggregatable, only 1Hour is passed."""
        mock_get_db.return_value = MagicMock()
        mock_agg_instance = MagicMock()
        mock_agg_instance.aggregate_missing_timeframes.return_value = {"1Hour": 5}
        mock_agg_cls.return_value = mock_agg_instance

        config = ProbeRunConfig(
            symbols=["AAPL"],
            timeframes=["1Hour", "1Day"],
        )
        runner = ProbeRunner(config)
        runner._ensure_timeframes_populated()

        call_kwargs = mock_agg_instance.aggregate_missing_timeframes.call_args.kwargs
        assert call_kwargs["target_timeframes"] == ["1Hour"]
