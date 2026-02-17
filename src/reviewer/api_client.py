"""HTTP client for reviewer service to call backend internal APIs.

The reviewer service does NOT access the database directly. All data
reads and writes go through the backend's /api/internal/ endpoints
via this client.
"""

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# Default timeout for HTTP calls (seconds)
_DEFAULT_TIMEOUT = 30.0


class ReviewerApiClient:
    """HTTP client wrapping backend internal API calls.

    Used by CheckRunner, baseline computation, and the orchestrator
    to read fills/profiles and write computed results.
    """

    def __init__(self, base_url: str, timeout: float = _DEFAULT_TIMEOUT) -> None:
        """Initialize the API client.

        Args:
            base_url: Backend base URL (e.g. "http://localhost:8000")
            timeout: HTTP request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        logger.info("ReviewerApiClient initialized: base_url=%s", self.base_url)

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        """Make a GET request and return parsed JSON.

        Args:
            path: URL path (e.g. "/api/internal/accounts/1/fills")
            params: Optional query parameters

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: On 4xx/5xx responses
        """
        url = f"{self.base_url}{path}"
        logger.debug("GET %s params=%s", url, params)
        response = httpx.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _put(self, path: str, json_body: dict) -> Any:
        """Make a PUT request and return parsed JSON.

        Args:
            path: URL path
            json_body: Request body dict

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: On 4xx/5xx responses
        """
        url = f"{self.base_url}{path}"
        logger.debug("PUT %s", url)
        response = httpx.put(url, json=json_body, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Fill data
    # ------------------------------------------------------------------

    def get_fills(
        self,
        account_id: int,
        lookback_days: int,
        symbol: Optional[str] = None,
    ) -> list[dict]:
        """Get fills with decision contexts for an account.

        Args:
            account_id: User account ID
            lookback_days: Number of days to look back
            symbol: Optional symbol filter

        Returns:
            List of fill dicts with context data
        """
        params: dict[str, Any] = {"lookback_days": lookback_days}
        if symbol:
            params["symbol"] = symbol

        data = self._get(f"/api/internal/accounts/{account_id}/fills", params=params)
        fills = data.get("fills", [])
        logger.debug(
            "Fetched %d fills for account_id=%s (lookback=%d)",
            len(fills), account_id, lookback_days,
        )
        return fills

    # ------------------------------------------------------------------
    # Profile data
    # ------------------------------------------------------------------

    def get_profile(self, account_id: int) -> dict:
        """Get user profile including balance, risk settings, and stats.

        Args:
            account_id: User account ID

        Returns:
            Profile dict with account_balance, risk_profile, profile, stats
        """
        data = self._get(f"/api/internal/accounts/{account_id}/profile")
        logger.debug("Fetched profile for account_id=%s", account_id)
        return data

    # ------------------------------------------------------------------
    # Market data (uses existing public API)
    # ------------------------------------------------------------------

    def get_ohlcv_bars(
        self,
        symbol: str,
        timeframe: str,
        end: Optional[str] = None,
        last_n_bars: Optional[int] = None,
    ) -> list[dict]:
        """Fetch OHLCV bars from the market data API.

        Args:
            symbol: Ticker symbol
            timeframe: Bar timeframe (e.g. "15Min", "1Day")
            end: Optional end timestamp (ISO-8601)
            last_n_bars: Optional number of most recent bars

        Returns:
            List of bar dicts with timestamp, open, high, low, close, volume
        """
        params: dict[str, Any] = {
            "symbol": symbol,
            "timeframe": timeframe,
        }
        if end:
            params["end"] = end
        if last_n_bars:
            params["last_n_bars"] = last_n_bars

        try:
            data = self._get("/api/v1/marketdata", params=params)
            bars = data.get("bars", [])
            logger.debug(
                "Fetched %d bars for %s/%s", len(bars), symbol, timeframe,
            )
            return bars
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.warning("No bars found for %s/%s", symbol, timeframe)
                return []
            raise

    # ------------------------------------------------------------------
    # Write: baseline stats
    # ------------------------------------------------------------------

    def save_baseline_stats(self, account_id: int, stats: dict) -> None:
        """Save computed baseline stats to user_profiles.stats.

        Args:
            account_id: User account ID
            stats: Computed baseline stats dict
        """
        self._put(
            f"/api/internal/accounts/{account_id}/baseline-stats",
            json_body={"stats": stats},
        )
        logger.info("Saved baseline stats for account_id=%s", account_id)

    # ------------------------------------------------------------------
    # Write: inferred context
    # ------------------------------------------------------------------

    def save_inferred_context(self, fill_id: int, context: dict) -> None:
        """Merge entry quality results into decision_contexts.inferred_context.

        Args:
            fill_id: Trade fill ID
            context: Dict to merge into inferred_context JSONB
        """
        self._put(
            f"/api/internal/fills/{fill_id}/inferred-context",
            json_body={"inferred_context": context},
        )
        logger.info("Saved inferred context for fill_id=%s", fill_id)

    # ------------------------------------------------------------------
    # Active accounts
    # ------------------------------------------------------------------

    def get_active_accounts(self, active_since_days: int = 30) -> list[int]:
        """List account IDs with recent trading activity.

        Args:
            active_since_days: Look back this many days for activity

        Returns:
            List of account IDs
        """
        data = self._get(
            "/api/internal/accounts",
            params={"active_since_days": active_since_days},
        )
        account_ids = data.get("account_ids", [])
        logger.debug("Found %d active accounts", len(account_ids))
        return account_ids
