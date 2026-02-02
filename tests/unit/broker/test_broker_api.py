from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.api import router
from src.api.broker import get_snaptrade_client, get_db
from src.data.database.broker_models import SnapTradeUser

client = TestClient(router)

def test_connect_broker_endpoint():
    # Mock deps
    mock_db = MagicMock(spec=Session)
    mock_snap_client = MagicMock()
    
    # Mock DB query for existing user
    mock_db.query.return_value.filter.return_value.first.return_value = SnapTradeUser(
        user_account_id=1,
        snaptrade_user_id="u1",
        snaptrade_user_secret="s1" 
    )
    
    # Mock client methods
    mock_snap_client.generate_connection_link.return_value = "http://redirect.com"

    # Override dependencies
    router.dependency_overrides_provider[get_db] = lambda: mock_db
    router.dependency_overrides_provider[get_snaptrade_client] = lambda: mock_snap_client

    response = client.post("/api/trading-buddy/connect", json={"user_id": 1})
    
    assert response.status_code == 200
    assert response.json() == {"redirect_url": "http://redirect.com"}

def test_sync_data_endpoint():
    # Mock deps
    mock_db = MagicMock(spec=Session)
    mock_snap_client = MagicMock()
    
    mock_user = SnapTradeUser(user_account_id=1, snaptrade_user_id="u1", snaptrade_user_secret="s1")
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    
    mock_snap_client.get_accounts.return_value = [{"id": "acc1", "name": "Test Broker", "brokerage_authorization_id": "auth1"}]
    mock_snap_client.get_activities.return_value = []

    router.dependency_overrides_provider[get_db] = lambda: mock_db
    router.dependency_overrides_provider[get_snaptrade_client] = lambda: mock_snap_client
    
    response = client.post("/api/trading-buddy/sync?user_id=1")
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
