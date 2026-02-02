from datetime import datetime, timezone
from src.data.database.broker_models import SnapTradeUser, BrokerConnection, TradeHistory

def test_snaptrade_user_model():
    user = SnapTradeUser(
        user_account_id=1,
        snaptrade_user_id="test_user",
        snaptrade_user_secret="test_secret"
    )
    assert user.user_account_id == 1
    assert user.snaptrade_user_id == "test_user"
    assert user.snaptrade_user_secret == "test_secret"

def test_broker_connection_model():
    conn = BrokerConnection(
        brokerage_name="Robinhood",
        brokerage_slug="robinhood",
        authorization_id="auth_123",
        meta={"name": "My Account"}
    )
    assert conn.brokerage_name == "Robinhood"
    assert conn.brokerage_slug == "robinhood"
    assert conn.authorization_id == "auth_123"
    assert conn.meta["name"] == "My Account"

def test_trade_history_model():
    trade = TradeHistory(
        symbol="AAPL",
        side="BUY",
        quantity=10.0,
        price=150.0,
        executed_at=datetime.now(timezone.utc),
        external_trade_id="trade_123",
        raw_data={"foo": "bar"}
    )
    assert trade.symbol == "AAPL"
    assert trade.side == "BUY"
    assert trade.quantity == 10.0
    assert trade.files is not None  # Should have default empty or None
