"""Strategy probe system for evaluating 100 TA-Lib strategies.

Auto-registers all strategies on import.
"""

import logging

from src.strats_prob.registry import register_strategies

logger = logging.getLogger(__name__)


def _auto_register() -> None:
    """Import and register all strategy definitions."""
    try:
        from src.strats_prob.strategies import ALL_STRATEGIES
        register_strategies(ALL_STRATEGIES)
        logger.info("Auto-registered %d strategies", len(ALL_STRATEGIES))
    except ImportError:
        logger.warning("Could not import strategies — registry will be empty")


_auto_register()
