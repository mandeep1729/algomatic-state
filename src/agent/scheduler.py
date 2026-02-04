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

            logger.debug(
                "Data fetch: %d rows, range=%s to %s, latest_close=%.4f",
                len(df), df.index[0], df.index[-1], float(df["close"].iloc[-1]),
            )

            # 4. Compute features
            features = pipeline.compute(df)
            if features.empty:
                logger.warning("Feature computation produced empty result")
                await asyncio.sleep(interval)
                continue

            momentum_col = strategy_config.momentum_feature
            nan_count = int(features[momentum_col].isna().sum()) if momentum_col in features.columns else -1
            logger.debug(
                "Features computed: shape=%s, %s NaN count=%d",
                features.shape, momentum_col, nan_count,
            )

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

                notional = order.quantity * current_price
                logger.debug(
                    "Order created: %s %s qty=%.4f price=%.4f notional=$%.2f",
                    order.side.value, order.symbol, order.quantity, current_price, notional,
                )

                # Account snapshot before risk check
                account = client.get_account()
                positions = client.get_positions()
                logger.debug(
                    "Account snapshot: equity=$%.2f buying_power=$%.2f positions=%d",
                    account.equity, account.buying_power, len(positions),
                )

                # Risk check
                violations = risk_manager.check_order(order, price=current_price, account=account, positions=positions)
                if violations:
                    for v in violations:
                        logger.warning("Risk violation — order rejected", extra={"violation": str(v)})
                    continue

                logger.debug("All risk checks passed for %s", order.symbol)

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
