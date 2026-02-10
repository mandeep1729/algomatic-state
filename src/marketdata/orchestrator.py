"""Orchestrator that wires the messaging bus to the MarketDataService."""

import logging
from typing import Optional

from src.marketdata.base import MarketDataProvider
from src.marketdata.service import MarketDataService
from src.messaging.base import MessageBusBase
from src.messaging.bus import get_message_bus
from src.messaging.events import Event, EventType

logger = logging.getLogger(__name__)


class MarketDataOrchestrator:
    """Listens for ``MARKET_DATA_REQUEST`` events and delegates to
    :class:`MarketDataService`, then publishes result events.

    Lifecycle::

        orchestrator = MarketDataOrchestrator(provider)
        orchestrator.start()   # subscribes to the bus
        ...
        orchestrator.stop()    # unsubscribes
    """

    def __init__(
        self,
        provider: MarketDataProvider,
        message_bus: Optional[MessageBusBase] = None,
    ) -> None:
        self.service = MarketDataService(provider)
        self._bus = message_bus or get_message_bus()
        self._started = False

    def start(self) -> None:
        """Subscribe to ``MARKET_DATA_REQUEST`` on the message bus."""
        if self._started:
            logger.warning("MarketDataOrchestrator already started")
            return
        self._bus.subscribe(EventType.MARKET_DATA_REQUEST, self._handle_request)
        self._started = True
        logger.info("MarketDataOrchestrator started (provider=%s)", self.service.provider.source_name)

    def stop(self) -> None:
        """Unsubscribe from the message bus."""
        if not self._started:
            return
        self._bus.unsubscribe(EventType.MARKET_DATA_REQUEST, self._handle_request)
        self._started = False
        logger.info("MarketDataOrchestrator stopped")

    def _handle_request(self, event: Event) -> None:
        """Handle an incoming ``MARKET_DATA_REQUEST``.

        Expected payload keys:
            - ``symbol`` (str): Ticker symbol.
            - ``timeframes`` (list[str]): Timeframes to ensure.
            - ``start`` (datetime | None): Start of range.
            - ``end`` (datetime | None): End of range.

        Publishes ``MARKET_DATA_UPDATED`` per timeframe that received
        new bars, or a single ``MARKET_DATA_FAILED`` on error.
        """
        payload = event.payload
        symbol = payload.get("symbol", "")
        timeframes = payload.get("timeframes", [])
        start = payload.get("start")
        end = payload.get("end")

        logger.info(
            "MarketDataOrchestrator handling request: symbol=%s, timeframes=%s (correlation_id=%s)",
            symbol, timeframes, event.correlation_id,
        )

        try:
            result = self.service.ensure_data(symbol, timeframes, start, end)

            for tf, new_bars in result.items():
                if new_bars > 0:
                    self._bus.publish(Event(
                        event_type=EventType.MARKET_DATA_UPDATED,
                        payload={
                            "symbol": symbol,
                            "timeframe": tf,
                            "new_bars": new_bars,
                        },
                        source="MarketDataOrchestrator",
                        correlation_id=event.correlation_id,
                    ))

        except Exception as e:
            logger.error(
                "MarketDataOrchestrator failed: symbol=%s, error=%s (correlation_id=%s)",
                symbol, e, event.correlation_id,
            )
            self._bus.publish(Event(
                event_type=EventType.MARKET_DATA_FAILED,
                payload={
                    "symbol": symbol,
                    "timeframes": timeframes,
                    "error": str(e),
                },
                source="MarketDataOrchestrator",
                correlation_id=event.correlation_id,
            ))
