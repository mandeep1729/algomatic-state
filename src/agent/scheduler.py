"""Agent scheduler — runs the fetch-compute-trade loop on a timer."""

import asyncio
import logging
from datetime import datetime

import httpx
import pandas as pd

from config.settings import StrategyConfig
from src.agent.config import AgentConfig
from src.agent.strategy import MomentumStrategy
from src.execution.client import AlpacaClient
from src.execution.order_manager import OrderManager, SignalDirection
from src.execution.risk_manager import RiskManager, RiskConfig
from src.features.pipeline import FeaturePipeline

logger = logging.getLogger(__name__)


async def run_agent_loop(
    agent_config: AgentConfig,
    strategy_config: StrategyConfig,
) -> None:
    """Run the momentum agent loop indefinitely.

    Each iteration:
    1. Check whether the market is open.
    2. Fetch OHLCV data via the internal ``/market-data`` endpoint.
    3. Compute features.
    4. Generate signals.
    5. Risk-check and submit orders.
    """
    client = AlpacaClient(paper=agent_config.paper)
    order_manager = OrderManager(client)
    risk_manager = RiskManager(client, RiskConfig())
    risk_manager.initialize()

    strategy = MomentumStrategy(
        config=strategy_config,
        symbol=agent_config.symbol,
        position_size=agent_config.position_size_dollars,
    )

    pipeline = FeaturePipeline.default()
    base_url = f"http://127.0.0.1:{agent_config.api_port}"
    interval = agent_config.interval_minutes * 60

    logger.info(
        "Agent loop started",
        extra={
            "symbol": agent_config.symbol,
            "interval_minutes": agent_config.interval_minutes,
            "data_provider": agent_config.data_provider,
        },
    )

    while True:
        try:
            # 1. Market-open check
            if not client.is_market_open():
                logger.info("Market is closed, sleeping")
                await asyncio.sleep(interval)
                continue

            # 2. Fetch data from internal API
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"{base_url}/market-data",
                    params={
                        "symbol": agent_config.symbol,
                        "lookback_days": agent_config.lookback_days,
                    },
                    timeout=120,
                )
                resp.raise_for_status()
                payload = resp.json()

            records = payload.get("data", [])
            if not records:
                logger.warning("No market data returned")
                await asyncio.sleep(interval)
                continue

            # 3. Build DataFrame
            df = pd.DataFrame(records)
            ts_col = "timestamp" if "timestamp" in df.columns else "index"
            df[ts_col] = pd.to_datetime(df[ts_col])
            df = df.set_index(ts_col).sort_index()

            # 4. Compute features
            features = pipeline.compute(df)
            if features.empty:
                logger.warning("Feature computation produced empty result")
                await asyncio.sleep(interval)
                continue

            # 5. Generate signals
            signals = strategy.generate_signals(features, timestamp=datetime.now())

            for signal in signals:
                if signal.direction == SignalDirection.FLAT:
                    logger.info(
                        "Signal is FLAT, no action",
                        extra={"momentum": signal.metadata.momentum_value},
                    )
                    continue

                # Convert signal to order
                current_price = float(df["close"].iloc[-1])
                order = order_manager.signal_to_order(signal, current_price=current_price)
                if order is None:
                    continue

                # Risk check
                violations = risk_manager.check_order(order, price=current_price)
                if violations:
                    for v in violations:
                        logger.warning("Risk violation — order rejected", extra={"violation": str(v)})
                    continue

                # Submit
                submitted = order_manager.submit_order(order)
                logger.info(
                    "Order submitted",
                    extra={
                        "symbol": submitted.symbol,
                        "side": str(submitted.side),
                        "quantity": submitted.quantity,
                        "broker_id": submitted.broker_order_id,
                    },
                )

        except Exception:
            logger.exception("Error in agent loop iteration")

        await asyncio.sleep(interval)
