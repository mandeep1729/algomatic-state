from unittest.mock import MagicMock, patch
import pytest
from src.execution.snaptrade_client import SnapTradeClient

class TestSnapTradeClient:
    @pytest.fixture
    def client(self):
        with patch("src.execution.snaptrade_client.SnapTrade") as mock_sdk:
            client = SnapTradeClient()
            client.client = mock_sdk
            yield client

    def test_register_user(self, client):
        mock_response = MagicMock()
        mock_response.body = {"user_id": "u1", "user_secret": "s1"}
        client.client.authentication.register_snap_trade_user.return_value = mock_response

        result = client.register_user("test_user")
        assert result["user_id"] == "u1"
        assert result["user_secret"] == "s1"
        client.client.authentication.register_snap_trade_user.assert_called_with(user_id="test_user")

    def test_generate_connection_link(self, client):
        mock_response = MagicMock()
        mock_response.body = {"login_redirect_url": "http://test.com"}
        client.client.authentication.login_snap_trade_user.return_value = mock_response

        link = client.generate_connection_link("u1", "s1")
        assert link == "http://test.com"

    def test_get_accounts(self, client):
        mock_response = MagicMock()
        mock_response.body = [{"id": "acc1"}]
        client.client.account_information.list_user_accounts.return_value = mock_response

        accounts = client.get_accounts("u1", "s1")
        assert len(accounts) == 1
        assert accounts[0]["id"] == "acc1"

    def test_get_activities(self, client):
        # Mock list_user_accounts
        mock_accounts = MagicMock()
        mock_accounts.body = [{"id": "acc1"}]
        client.client.account_information.list_user_accounts.return_value = mock_accounts

        # Mock get_activities
        mock_activities = MagicMock()
        mock_activities.body = [{"id": "act1"}]
        client.client.transactions_and_reporting.get_activities.return_value = mock_activities

        activities = client.get_activities("u1", "s1")
        assert len(activities) == 1
        assert activities[0]["id"] == "act1"
