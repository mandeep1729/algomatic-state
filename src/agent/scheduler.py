"""Agent scheduler — runs the fetch-compute-trade loop on a timer."""

import asyncio
import logging
from datetime import datetime
from typing import Literal, Union

import httpx
import pandas as pd

from config.settings import StrategyConfig
from src.agent.breakout_config import BreakoutAgentConfig, BreakoutStrategyConfig
from src.agent.breakout_strategy import BreakoutStrategy
from src.agent.config import AgentConfig
from src.agent.contrarian_config import ContrarianAgentConfig, ContrarianStrategyConfig
from src.agent.contrarian_strategy import ContrarianStrategy
from src.agent.strategy import MomentumStrategy
from src.agent.vwap_config import VWAPAgentConfig, VWAPStrategyConfig
from src.agent.vwap_strategy import VWAPReversionStrategy
from src.execution.client import AlpacaClient
from src.execution.order_manager import OrderManager, SignalDirection
from src.execution.risk_manager import RiskManager, RiskConfig
from src.features.pipeline import FeaturePipeline

logger = logging.getLogger(__name__)

# Type aliases for clarity
AgentConfigType = Union[AgentConfig, ContrarianAgentConfig, BreakoutAgentConfig, VWAPAgentConfig]
StrategyConfigType = Union[StrategyConfig, ContrarianStrategyConfig, BreakoutStrategyConfig, VWAPStrategyConfig]
StrategyType = Literal["momentum", "contrarian", "breakout", "vwap"]


def _create_strategy(
    strategy_type: StrategyType,
    strategy_config: StrategyConfigType,
    agent_config: AgentConfigType,
):
    """Create the appropriate strategy instance based on strategy_type."""
    if strategy_type == "contrarian":
        return ContrarianStrategy(
            config=strategy_config,
            symbol=agent_config.symbol,
            position_size=agent_config.position_size_dollars,
        )
    elif strategy_type == "breakout":
        return BreakoutStrategy(
            config=strategy_config,
            symbol=agent_config.symbol,
            position_size=agent_config.position_size_dollars,
        )
    elif strategy_type == "vwap":
        return VWAPReversionStrategy(
            config=strategy_config,
            symbol=agent_config.symbol,
            position_size=agent_config.position_size_dollars,
        )
    else:
        return MomentumStrategy(
            config=strategy_config,
            symbol=agent_config.symbol,
            position_size=agent_config.position_size_dollars,
        )


def _get_signal_feature(strategy_type: StrategyType, strategy_config: StrategyConfigType) -> str:
    """Get the primary feature name used by the strategy for logging."""
    if strategy_type == "breakout":
        return strategy_config.breakout_feature
    elif strategy_type == "vwap":
        return strategy_config.vwap_feature
    else:
        return strategy_config.momentum_feature


async def run_agent_loop(
    agent_config: AgentConfigType,
    strategy_config: StrategyConfigType,
    strategy_type: StrategyType = "momentum",
) -> None:
    """Run the trading agent loop indefinitely.

    Each iteration:
    1. Check whether the market is open.
    2. Fetch OHLCV data via the internal ``/market-data`` endpoint.
    3. Compute features.
    4. Generate signals.
    5. Risk-check and submit orders.

    Args:
        agent_config: Agent configuration.
        strategy_config: Strategy configuration.
        strategy_type: Which strategy to use.
    """
    client = AlpacaClient(paper=agent_config.paper)
    order_manager = OrderManager(client)
    risk_manager = RiskManager(client, RiskConfig())
    risk_manager.initialize()

    strategy = _create_strategy(strategy_type, strategy_config, agent_config)

    pipeline = FeaturePipeline.default()
    base_url = f"http://127.0.0.1:{agent_config.api_port}"
    interval = agent_config.interval_minutes * 60

    logger.info(
        "Agent loop started",
        extra={
            "strategy_type": strategy_type,
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

            signal_feature = _get_signal_feature(strategy_type, strategy_config)
            nan_count = int(features[signal_feature].isna().sum()) if signal_feature in features.columns else -1
            logger.debug(
                "Features computed: shape=%s, %s NaN count=%d",
                features.shape, signal_feature, nan_count,
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

                # Convert signal to order with ATR-based bracket stops
                current_price = float(df["close"].iloc[-1])

                stop_loss_price = None
                take_profit_price = None
                if "atr_14" in features.columns:
                    atr = float(features["atr_14"].iloc[-1])
                    if atr > 0:
                        if signal.direction == SignalDirection.LONG:
                            stop_loss_price = round(current_price - agent_config.atr_stop_mult * atr, 2)
                            take_profit_price = round(current_price + agent_config.atr_target_mult * atr, 2)
                        else:
                            stop_loss_price = round(current_price + agent_config.atr_stop_mult * atr, 2)
                            take_profit_price = round(current_price - agent_config.atr_target_mult * atr, 2)
                        logger.debug(
                            "ATR bracket: atr=%.4f stop_loss=%.2f take_profit=%.2f",
                            atr, stop_loss_price, take_profit_price,
                        )
                    else:
                        logger.warning("ATR is zero or negative for %s — rejecting order (no bracket protection)", ticker)
                        continue
                else:
                    logger.warning("atr_14 not in features for %s — rejecting order (no bracket protection)", ticker)
                    continue

                order = order_manager.signal_to_order(
                    signal,
                    current_price=current_price,
                    strategy_name=strategy_type,
                    stop_loss_price=stop_loss_price,
                    take_profit_price=take_profit_price,
                )
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
