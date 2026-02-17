"""Tests for trade intent domain objects.

Tests cover:
- TradeIntent creation and validation
- Price relationship validation for long and short trades
- Risk/reward calculations
- Serialization and deserialization
"""

import pytest
from datetime import datetime

from src.trade.intent import (
    TradeIntent,
    TradeDirection,
    TradeIntentStatus,
)


class TestTradeDirection:
    """Tests for TradeDirection enum."""

    def test_long_direction(self):
        """Test LONG direction value."""
        assert TradeDirection.LONG.value == "long"

    def test_short_direction(self):
        """Test SHORT direction value."""
        assert TradeDirection.SHORT.value == "short"

    def test_direction_from_string(self):
        """Test creating direction from string."""
        long_dir = TradeDirection("long")
        short_dir = TradeDirection("short")
        assert long_dir == TradeDirection.LONG
        assert short_dir == TradeDirection.SHORT


class TestTradeIntentStatus:
    """Tests for TradeIntentStatus enum."""

    def test_all_statuses_exist(self):
        """Test that all expected statuses exist."""
        expected_statuses = [
            "DRAFT",
            "PENDING_EVALUATION",
            "EVALUATED",
            "APPROVED",
            "REJECTED",
            "EXECUTED",
            "CANCELLED",
        ]
        for status_name in expected_statuses:
            assert hasattr(TradeIntentStatus, status_name)


class TestTradeIntentCreation:
    """Tests for TradeIntent creation."""

    def test_create_long_trade_valid(self):
        """Test creating a valid long trade."""
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
        )

        assert intent.user_id == 1
        assert intent.symbol == "AAPL"
        assert intent.direction == TradeDirection.LONG
        assert intent.entry_price == 150.0
        assert intent.stop_loss == 145.0
        assert intent.profit_target == 160.0

    def test_create_short_trade_valid(self):
        """Test creating a valid short trade."""
        intent = TradeIntent(
            user_id=1,
            symbol="TSLA",
            direction=TradeDirection.SHORT,
            timeframe="15Min",
            entry_price=250.0,
            stop_loss=260.0,
            profit_target=240.0,
        )

        assert intent.direction == TradeDirection.SHORT
        assert intent.entry_price == 250.0
        assert intent.stop_loss == 260.0
        assert intent.profit_target == 240.0

    def test_symbol_uppercase_conversion(self):
        """Test that symbols are converted to uppercase."""
        intent = TradeIntent(
            user_id=1,
            symbol="aapl",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
        )

        assert intent.symbol == "AAPL"

    def test_direction_string_conversion(self):
        """Test that direction strings are converted to enums."""
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction="long",
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
        )

        assert intent.direction == TradeDirection.LONG
        assert isinstance(intent.direction, TradeDirection)

    def test_status_string_conversion(self):
        """Test that status strings are converted to enums."""
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
            status="evaluated",
        )

        assert intent.status == TradeIntentStatus.EVALUATED
        assert isinstance(intent.status, TradeIntentStatus)

    def test_default_status_is_draft(self):
        """Test that default status is DRAFT."""
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
        )

        assert intent.status == TradeIntentStatus.DRAFT

    def test_created_at_defaults_to_now(self):
        """Test that created_at defaults to current time."""
        before = datetime.utcnow()
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
        )
        after = datetime.utcnow()

        assert before <= intent.created_at <= after


class TestLongTradeValidation:
    """Tests for long trade price validation."""

    def test_long_valid_prices(self):
        """Test that valid long trade prices pass validation."""
        # Should not raise
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
        )
        assert intent.entry_price == 150.0

    def test_long_stop_loss_above_entry_fails(self):
        """Test that long trade with stop loss >= entry price fails."""
        with pytest.raises(ValueError) as exc_info:
            TradeIntent(
                user_id=1,
                symbol="AAPL",
                direction=TradeDirection.LONG,
                timeframe="1Hour",
                entry_price=150.0,
                stop_loss=150.0,  # Equal to entry, should fail
                profit_target=160.0,
            )

        assert "stop_loss" in str(exc_info.value)
        assert "must be below" in str(exc_info.value)

    def test_long_stop_loss_equal_to_entry_fails(self):
        """Test that long trade with stop loss equal to entry price fails."""
        with pytest.raises(ValueError):
            TradeIntent(
                user_id=1,
                symbol="AAPL",
                direction=TradeDirection.LONG,
                timeframe="1Hour",
                entry_price=150.0,
                stop_loss=150.1,  # Above entry
                profit_target=160.0,
            )

    def test_long_profit_target_below_entry_fails(self):
        """Test that long trade with profit target <= entry price fails."""
        with pytest.raises(ValueError) as exc_info:
            TradeIntent(
                user_id=1,
                symbol="AAPL",
                direction=TradeDirection.LONG,
                timeframe="1Hour",
                entry_price=150.0,
                stop_loss=145.0,
                profit_target=150.0,  # Equal to entry
            )

        assert "profit_target" in str(exc_info.value)
        assert "must be above" in str(exc_info.value)


class TestShortTradeValidation:
    """Tests for short trade price validation."""

    def test_short_valid_prices(self):
        """Test that valid short trade prices pass validation."""
        # Should not raise
        intent = TradeIntent(
            user_id=1,
            symbol="TSLA",
            direction=TradeDirection.SHORT,
            timeframe="15Min",
            entry_price=250.0,
            stop_loss=260.0,
            profit_target=240.0,
        )
        assert intent.entry_price == 250.0

    def test_short_stop_loss_below_entry_fails(self):
        """Test that short trade with stop loss <= entry price fails."""
        with pytest.raises(ValueError) as exc_info:
            TradeIntent(
                user_id=1,
                symbol="TSLA",
                direction=TradeDirection.SHORT,
                timeframe="15Min",
                entry_price=250.0,
                stop_loss=250.0,  # Equal to entry
                profit_target=240.0,
            )

        assert "stop_loss" in str(exc_info.value)
        assert "must be above" in str(exc_info.value)

    def test_short_profit_target_above_entry_fails(self):
        """Test that short trade with profit target >= entry price fails."""
        with pytest.raises(ValueError) as exc_info:
            TradeIntent(
                user_id=1,
                symbol="TSLA",
                direction=TradeDirection.SHORT,
                timeframe="15Min",
                entry_price=250.0,
                stop_loss=260.0,
                profit_target=250.0,  # Equal to entry
            )

        assert "profit_target" in str(exc_info.value)
        assert "must be below" in str(exc_info.value)


class TestRiskRewardCalculations:
    """Tests for risk/reward ratio calculations."""

    def test_long_risk_per_share(self):
        """Test risk per share calculation for long trade."""
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
        )

        assert intent.risk_per_share == 5.0  # 150 - 145

    def test_short_risk_per_share(self):
        """Test risk per share calculation for short trade."""
        intent = TradeIntent(
            user_id=1,
            symbol="TSLA",
            direction=TradeDirection.SHORT,
            timeframe="15Min",
            entry_price=250.0,
            stop_loss=260.0,
            profit_target=240.0,
        )

        assert intent.risk_per_share == 10.0  # 260 - 250

    def test_long_reward_per_share(self):
        """Test reward per share calculation for long trade."""
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
        )

        assert intent.reward_per_share == 10.0  # 160 - 150

    def test_short_reward_per_share(self):
        """Test reward per share calculation for short trade."""
        intent = TradeIntent(
            user_id=1,
            symbol="TSLA",
            direction=TradeDirection.SHORT,
            timeframe="15Min",
            entry_price=250.0,
            stop_loss=260.0,
            profit_target=240.0,
        )

        assert intent.reward_per_share == 10.0  # 250 - 240

    def test_risk_reward_ratio(self):
        """Test risk:reward ratio calculation."""
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
        )

        # Risk is 5, Reward is 10, so ratio is 10/5 = 2.0
        assert intent.risk_reward_ratio == 2.0

    def test_risk_reward_ratio_one_to_one(self):
        """Test 1:1 risk:reward ratio."""
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=155.0,
        )

        assert intent.risk_reward_ratio == 1.0

    def test_risk_reward_ratio_infinity_on_zero_risk(self):
        """Test that infinity is returned when risk is zero (invalid trade)."""
        # This would actually be caught in validation, but test the property
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
        )

        # Manually set to create zero risk (bypassing validation)
        intent.stop_loss = 150.0  # Same as entry
        assert intent.risk_reward_ratio == float('inf')


class TestPositionRiskCalculations:
    """Tests for total position risk calculations."""

    def test_total_risk_with_position_size(self):
        """Test total risk calculation with position size."""
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
            position_size=100,
        )

        # Risk per share is 5, position size is 100, so total is 500
        assert intent.total_risk == 500.0

    def test_total_risk_without_position_size(self):
        """Test that total risk is None when position size is not provided."""
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
        )

        assert intent.total_risk is None

    def test_total_risk_with_large_position(self):
        """Test total risk with large position size."""
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
            position_size=1000,
        )

        assert intent.total_risk == 5000.0


class TestSerializationDeserialization:
    """Tests for to_dict and from_dict methods."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        created_at = datetime.utcnow()
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
            position_size=100,
            created_at=created_at,
            intent_id=123,
            account_id=456,
            status=TradeIntentStatus.EVALUATED,
            rationale="Strong uptrend",
        )

        result = intent.to_dict()

        assert result["intent_id"] == 123
        assert result["user_id"] == 1
        assert result["account_id"] == 456
        assert result["symbol"] == "AAPL"
        assert result["direction"] == "long"
        assert result["entry_price"] == 150.0
        assert result["status"] == "evaluated"
        assert result["rationale"] == "Strong uptrend"
        assert result["risk_reward_ratio"] == 2.0
        assert result["total_risk"] == 500.0

    def test_from_dict(self):
        """Test creation from dictionary."""
        created_at = datetime.utcnow()
        data = {
            "intent_id": 123,
            "user_id": 1,
            "account_id": 456,
            "symbol": "aapl",
            "direction": "long",
            "timeframe": "1Hour",
            "entry_price": 150.0,
            "stop_loss": 145.0,
            "profit_target": 160.0,
            "position_size": 100,
            "position_value": 15000,
            "status": "evaluated",
            "created_at": created_at.isoformat(),
            "rationale": "Strong uptrend",
            "metadata": {"broker": "alpaca"},
        }

        intent = TradeIntent.from_dict(data)

        assert intent.intent_id == 123
        assert intent.user_id == 1
        assert intent.symbol == "AAPL"
        assert intent.direction == TradeDirection.LONG
        assert intent.status == TradeIntentStatus.EVALUATED
        assert intent.rationale == "Strong uptrend"
        assert intent.metadata == {"broker": "alpaca"}

    def test_roundtrip_serialization(self):
        """Test that serialization and deserialization are consistent."""
        original = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
            position_size=100,
            rationale="Test trade",
            intent_id=123,
            account_id=456,
        )

        serialized = original.to_dict()
        deserialized = TradeIntent.from_dict(serialized)

        assert deserialized.user_id == original.user_id
        assert deserialized.symbol == original.symbol
        assert deserialized.direction == original.direction
        assert deserialized.entry_price == original.entry_price
        assert deserialized.stop_loss == original.stop_loss
        assert deserialized.profit_target == original.profit_target
        assert deserialized.position_size == original.position_size

    def test_from_dict_with_missing_optional_fields(self):
        """Test from_dict with minimal required fields."""
        data = {
            "user_id": 1,
            "symbol": "AAPL",
            "direction": "long",
            "timeframe": "1Hour",
            "entry_price": 150.0,
            "stop_loss": 145.0,
            "profit_target": 160.0,
            "created_at": datetime.utcnow().isoformat(),
        }

        intent = TradeIntent.from_dict(data)

        assert intent.user_id == 1
        assert intent.intent_id is None
        assert intent.account_id is None
        assert intent.position_size is None
        assert intent.rationale is None
        assert intent.metadata == {}


class TestMetadata:
    """Tests for metadata handling."""

    def test_metadata_default_empty_dict(self):
        """Test that metadata defaults to empty dict."""
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
        )

        assert intent.metadata == {}

    def test_metadata_custom_values(self):
        """Test that custom metadata can be provided."""
        metadata = {"broker": "alpaca", "account_type": "margin"}
        intent = TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
            metadata=metadata,
        )

        assert intent.metadata == metadata
        assert intent.metadata["broker"] == "alpaca"
