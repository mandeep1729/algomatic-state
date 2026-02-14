"""Unit tests for ProbeRunConfig persist_trades parameter."""

import logging

from src.strats_prob.runner import ProbeRunConfig


class TestProbeRunConfigPersistTrades:
    """Tests for the persist_trades field on ProbeRunConfig."""

    def test_persist_trades_defaults_to_false(self):
        """persist_trades is False by default for backward compatibility."""
        config = ProbeRunConfig(symbols=["AAPL"])
        assert config.persist_trades is False

    def test_persist_trades_can_be_set_true(self):
        """persist_trades can be explicitly set to True."""
        config = ProbeRunConfig(symbols=["AAPL"], persist_trades=True)
        assert config.persist_trades is True

    def test_persist_trades_can_be_set_false(self):
        """persist_trades can be explicitly set to False."""
        config = ProbeRunConfig(symbols=["SPY"], persist_trades=False)
        assert config.persist_trades is False

    def test_run_id_auto_generated(self):
        """run_id is auto-generated when not provided."""
        config = ProbeRunConfig(symbols=["AAPL"], persist_trades=True)
        assert config.run_id is not None
        assert len(config.run_id) == 8

    def test_persist_trades_logged_in_post_init(self, caplog):
        """persist_trades value is logged during __post_init__."""
        with caplog.at_level(logging.INFO, logger="src.strats_prob.runner"):
            config = ProbeRunConfig(symbols=["AAPL"], persist_trades=True)
        assert "persist_trades=True" in caplog.text

    def test_persist_trades_false_logged_in_post_init(self, caplog):
        """persist_trades=False is logged during __post_init__."""
        with caplog.at_level(logging.INFO, logger="src.strats_prob.runner"):
            config = ProbeRunConfig(symbols=["SPY"], persist_trades=False)
        assert "persist_trades=False" in caplog.text

    def test_default_config_backward_compatible(self):
        """Default config matches the original behavior before persist_trades was added."""
        config = ProbeRunConfig(symbols=["AAPL"])
        assert config.timeframes == ["15Min", "1Hour", "1Day"]
        assert config.risk_profiles == ["low", "medium", "high"]
        assert config.strategy_ids is None
        assert config.start is None
        assert config.end is None
        assert config.persist_trades is False


class TestCliPersistTradesArg:
    """Tests for --persist-trades CLI argument."""

    def test_persist_trades_flag_absent(self):
        """CLI defaults to persist_trades=False when flag is not passed."""
        from src.strats_prob.cli import parse_args
        args = parse_args(["--symbols", "AAPL"])
        assert args.persist_trades is False

    def test_persist_trades_flag_present(self):
        """CLI sets persist_trades=True when --persist-trades is passed."""
        from src.strats_prob.cli import parse_args
        args = parse_args(["--symbols", "AAPL", "--persist-trades"])
        assert args.persist_trades is True
