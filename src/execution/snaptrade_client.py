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
            logger.error("SnapTrade credentials not found in environment variables.")

        try:
            self.client = SnapTrade(
                consumer_key=self.consumer_key,
                client_id=self.client_id,
            )
        except Exception as e:
            logger.error(f"Failed to initialize SnapTrade client: {e}", exc_info=True)
            self.client = None

    def register_user(self, user_id: str) -> Optional[Dict[str, str]]:
        """Register a new user with SnapTrade.

        If the user already exists, deletes and re-registers them.

        Args:
            user_id: Internal user ID (will be used as SnapTrade userId)

        Returns:
            Dict containing 'user_id' and 'user_secret' or None if failed.
        """
        if not self.client:
            logger.debug("SnapTrade client not initialized, skipping %s", "register_user")
            return None

        try:
            # Register user
            response = self.client.authentication.register_snap_trade_user(
                user_id=user_id
            )
            return {
                "user_id": response.body["userId"],
                "user_secret": response.body["userSecret"],
            }
        except Exception as e:
            error_str = str(e)
            # Handle "user already exists" error
            if "already exist" in error_str or "1010" in error_str:
                logger.info(f"User {user_id} already exists in SnapTrade, deleting and re-registering")
                try:
                    # Delete existing user
                    self.client.authentication.delete_snap_trade_user(user_id=user_id)
                    # Re-register
                    response = self.client.authentication.register_snap_trade_user(
                        user_id=user_id
                    )
                    return {
                        "user_id": response.body["userId"],
                        "user_secret": response.body["userSecret"],
                    }
                except Exception as e2:
                    logger.error(f"Failed to re-register SnapTrade user after deletion: {e2}")
                    return None
            logger.error(f"Failed to register SnapTrade user: {e}")
            return None

    def generate_connection_link(
        self,
        user_id: str,
        user_secret: str,
        custom_redirect: Optional[str] = None,
        broker: Optional[str] = None,
    ) -> Optional[str]:
        """Generate a connection link for the user to connect a broker.

        Args:
            user_id: SnapTrade user ID
            user_secret: SnapTrade user secret
            custom_redirect: URL to redirect to after connection completes
            broker: Optional broker slug to pre-select (e.g., 'ALPACA')

        Returns:
            Redirect URI string or None.
        """
        if not self.client:
            logger.debug("SnapTrade client not initialized, skipping %s", "generate_connection_link")
            return None

        try:
            kwargs = {
                "user_id": user_id,
                "user_secret": user_secret,
            }
            if custom_redirect:
                kwargs["custom_redirect"] = custom_redirect
            if broker:
                kwargs["broker"] = broker

            response = self.client.authentication.login_snap_trade_user(**kwargs)
            return response.body.get("redirectURI")
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
            logger.debug("SnapTrade client not initialized, skipping %s", "get_holdings")
            return None

        try:
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
            logger.debug("SnapTrade client not initialized, skipping %s", "get_activities")
            return None

        try:
            # Build params
            kwargs = {
                "user_id": user_id,
                "user_secret": user_secret,
            }
            if start_date:
                kwargs["start_date"] = start_date.strftime("%Y-%m-%d")
            if end_date:
                kwargs["end_date"] = end_date.strftime("%Y-%m-%d")

            # Get all activities for user (API returns all accounts)
            response = self.client.transactions_and_reporting.get_activities(**kwargs)
            return response.body

        except Exception as e:
            logger.error(f"Failed to get activities: {e}")
            return None

    def get_accounts(self, user_id: str, user_secret: str) -> Optional[List[Dict[str, Any]]]:
        """List connected brokerage accounts."""
        if not self.client:
            logger.debug("SnapTrade client not initialized, skipping %s", "get_accounts")
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

    def list_brokerages(self) -> Optional[List[Dict[str, Any]]]:
        """List all SnapTrade-supported brokerages.

        Returns:
            List of brokerage dicts with fields like id, name, display_name,
            slug, aws_s3_logo_url, enabled, allows_trading, etc., or None on failure.
        """
        if not self.client:
            logger.debug("SnapTrade client not initialized, skipping %s", "list_brokerages")
            return None

        try:
            response = self.client.reference_data.list_all_brokerages()
            return response.body
        except Exception as e:
            logger.error("Failed to list brokerages: %s", e)
            return None

    def list_connections(
        self, user_id: str, user_secret: str
    ) -> Optional[List[Dict[str, Any]]]:
        """List user's brokerage authorization connections.

        Args:
            user_id: SnapTrade user ID
            user_secret: SnapTrade user secret

        Returns:
            List of authorization dicts with connection details and nested
            brokerage info, or None on failure.
        """
        if not self.client:
            logger.debug("SnapTrade client not initialized, skipping %s", "list_connections")
            return None

        try:
            response = self.client.connections.list_brokerage_authorizations(
                user_id=user_id,
                user_secret=user_secret,
            )
            return response.body
        except Exception as e:
            logger.error("Failed to list connections: %s", e)
            return None

    def remove_connection(
        self, authorization_id: str, user_id: str, user_secret: str
    ) -> bool:
        """Remove a brokerage authorization (disconnect a broker).

        Args:
            authorization_id: The SnapTrade authorization ID to remove
            user_id: SnapTrade user ID
            user_secret: SnapTrade user secret

        Returns:
            True if removed successfully, False otherwise.
        """
        if not self.client:
            logger.debug("SnapTrade client not initialized, skipping %s", "remove_connection")
            return False

        try:
            self.client.connections.remove_brokerage_authorization(
                authorization_id=authorization_id,
                user_id=user_id,
                user_secret=user_secret,
            )
            logger.info("Removed brokerage authorization: %s", authorization_id)
            return True
        except Exception as e:
            logger.error("Failed to remove connection %s: %s", authorization_id, e)
            return False
