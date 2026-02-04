"""Internal FastAPI endpoints for the momentum agent."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Query

from src.agent.config import AgentConfig
from src.data.loaders.database_loader import DatabaseLoader

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
    """Return OHLCV data, syncing missing bars from the configured provider."""
    config = _get_config()

    provider = _create_provider(config.data_provider)
    loader = DatabaseLoader(provider=provider, auto_fetch=True)

    end = datetime.now(timezone.utc).replace(tzinfo=None)
    start = end - timedelta(days=lookback_days)

    logger.info(
        "Loading market data",
        extra={"symbol": symbol, "start": str(start), "end": str(end)},
    )

    df = loader.load(symbol, start=start, end=end, timeframe="1Min")

    records = df.reset_index().to_dict(orient="records")
    # Convert timestamps to ISO strings for JSON serialisation
    for rec in records:
        ts = rec.get("timestamp") or rec.get("index")
        if ts is not None and hasattr(ts, "isoformat"):
            key = "timestamp" if "timestamp" in rec else "index"
            rec[key] = ts.isoformat()

    return {"symbol": symbol, "count": len(records), "data": records}
