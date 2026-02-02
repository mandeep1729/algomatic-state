"""Client wrapper for SnapTrade API.

Handles authentication, user registration, and data fetching from SnapTrade.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from snaptrade_client import SnapTrade
from pprint import pprint

logger = logging.getLogger(__name__)


class SnapTradeClient:
    """Wrapper for SnapTrade SDK."""

    def __init__(self):
        """Initialize SnapTrade client with credentials from environment."""
        self.client_id = os.environ.get("SNAPTRADE_CLIENT_ID")
        self.consumer_key = os.environ.get("SNAPTRADE_CONSUMER_KEY")

        if not self.client_id or not self.consumer_key:
            logger.warning("SnapTrade credentials not found in environment variables.")

        try:
            self.client = SnapTrade(
                consumer_key=self.consumer_key,
                client_id=self.client_id,
            )
            # Check status (optional, but good for verification)
            # status = self.client.api_status.check() 
            # logger.info(f"SnapTrade API Status: {status}")
        except Exception as e:
            logger.error(f"Failed to initialize SnapTrade client: {e}")
            self.client = None

    def register_user(self, user_id: str) -> Optional[Dict[str, str]]:
        """Register a new user with SnapTrade.

        Args:
            user_id: Internal user ID (will be used as SnapTrade userId)

        Returns:
            Dict containing 'user_id' and 'user_secret' or None if failed.
        """
        if not self.client:
            return None

        try:
            # Register user
            response = self.client.authentication.register_snap_trade_user(
                user_id=user_id
            )
            return {
                "user_id": response.body["user_id"],
                "user_secret": response.body["user_secret"],
            }
        except Exception as e:
            logger.error(f"Failed to register SnapTrade user: {e}")
            return None

    def generate_connection_link(self, user_id: str, user_secret: str) -> Optional[str]:
        """Generate a connection link for the user to connect a broker.

        Args:
            user_id: SnapTrade user ID
            user_secret: SnapTrade user secret

        Returns:
            Redirect URI string or None.
        """
        if not self.client:
            return None

        try:
            response = self.client.authentication.login_snap_trade_user(
                user_id=user_id,
                user_secret=user_secret,
                immediate_redirect=True # Optional, depends on desired flow
            )
            return response.body.get("login_redirect_url")
        except Exception as e:
            logger.error(f"Failed to generate connection link: {e}")
            return None

    def get_holdings(self, user_id: str, user_secret: str) -> Optional[List[Dict[str, Any]]]:
        """Get all holdings for a user across all accounts.

        Args:
            user_id: SnapTrade user ID
            user_secret: SnapTrade user secret

        Returns:
            List of holdings or None.
        """
        if not self.client:
            return None

        try:
            # accounts = self.client.account_information.list_user_accounts(
            #     user_id=user_id,
            #     user_secret=user_secret
            # )
            # For simplicity, getting all user holdings usually aggregates or we iterate
            response = self.client.account_information.get_all_user_holdings(
                user_id=user_id,
                user_secret=user_secret
            )
            return response.body
        except Exception as e:
            logger.error(f"Failed to get holdings: {e}")
            return None

    def get_activities(
        self, 
        user_id: str, 
        user_secret: str, 
        start_date: Optional[datetime] = None, 
        end_date: Optional[datetime] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Get trade activities/transactions for a user.

        Args:
             user_id: SnapTrade user ID
             user_secret: SnapTrade user secret
             start_date: Filter start date
             end_date: Filter end date

        Returns:
            List of activities or None.
        """
        if not self.client:
            return None

        try:
            # Note: The SDK might require specific formatting for dates
            params = {
                "user_id": user_id,
                "user_secret": user_secret,
            }
            if start_date:
                params["start_date"] = start_date.strftime("%Y-%m-%d")
            if end_date:
                params["end_date"] = end_date.strftime("%Y-%m-%d")
                
            # Usually we need to query per account, or use a "get_all" if available.
            # SnapTrade docs usually suggest getting accounts first, then activities per account.
            # But let's check if there's a global activities endpoint or we iterate.
            # For now, let's assume we fetch accounts and then activities for each.
            
            accounts = self.client.account_information.list_user_accounts(
                user_id=user_id,
                user_secret=user_secret
            )
            
            all_activities = []
            for account in accounts.body:
                activities = self.client.transactions_and_reporting.get_activities(
                    user_id=user_id,
                    user_secret=user_secret,
                    account_id=account["id"],
                    start_date=params.get("start_date"),
                    end_date=params.get("end_date")
                )
                all_activities.extend(activities.body)
                
            return all_activities

        except Exception as e:
            logger.error(f"Failed to get activities: {e}")
            return None

    def get_accounts(self, user_id: str, user_secret: str) -> Optional[List[Dict[str, Any]]]:
        """List connected brokerage accounts."""
        if not self.client:
             return None
        
        try:
            response = self.client.account_information.list_user_accounts(
                user_id=user_id,
                user_secret=user_secret
            )
            return response.body
        except Exception as e:
            logger.error(f"Failed to list accounts: {e}")
            return None
