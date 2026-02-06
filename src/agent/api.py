"""Internal FastAPI endpoints for the momentum agent."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Query

from src.agent.config import AgentConfig

logger = logging.getLogger(__name__)

app = FastAPI(title="Momentum Agent API")

_agent_config: AgentConfig | None = None


def set_config(config: AgentConfig) -> None:
    """Store the agent config so endpoints can access it."""
    global _agent_config
    _agent_config = config


def _get_config() -> AgentConfig:
    global _agent_config
    if _agent_config is None:
        _agent_config = AgentConfig()
    return _agent_config


def _create_provider(data_provider: str):
    """Create the appropriate MarketDataProvider."""
    if data_provider == "finnhub":
        from src.marketdata.finnhub_provider import FinnhubProvider
        return FinnhubProvider()
    else:
        from src.marketdata.alpaca_provider import AlpacaProvider
        return AlpacaProvider()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/market-data")
def market_data(
    symbol: str = Query(default="AAPL"),
    lookback_days: int = Query(default=5),
):
    """Return OHLCV data, syncing missing bars via the messaging bus."""
    from src.messaging.events import Event, EventType
    from src.messaging.bus import get_message_bus
    from src.data.database.connection import get_db_manager
    from src.data.database.market_repository import OHLCVRepository

    end = datetime.now(timezone.utc).replace(tzinfo=None)
    start = end - timedelta(days=lookback_days)

    logger.info(
        "Loading market data",
        extra={"symbol": symbol, "start": str(start), "end": str(end)},
    )

    # Request fresh data via the messaging bus (the orchestrator handles
    # fetching from the configured provider and inserting into the DB).
    bus = get_message_bus()
    bus.publish(Event(
        event_type=EventType.MARKET_DATA_REQUEST,
        payload={
            "symbol": symbol,
            "timeframes": ["1Min"],
            "start": start,
            "end": end,
        },
        source="agent.api",
    ))

    # Read from DB
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = OHLCVRepository(session)
        df = repo.get_bars(symbol.upper(), "1Min", start, end)

    records = df.reset_index().to_dict(orient="records")
    # Convert timestamps to ISO strings for JSON serialisation
    for rec in records:
        ts = rec.get("timestamp") or rec.get("index")
        if ts is not None and hasattr(ts, "isoformat"):
            key = "timestamp" if "timestamp" in rec else "index"
            rec[key] = ts.isoformat()

    return {"symbol": symbol, "count": len(records), "data": records}
