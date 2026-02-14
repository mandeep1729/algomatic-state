"""Strategy registry for probe system.

Maintains an in-memory registry of all strategy definitions and
optionally seeds them into the database.
"""

import logging
from typing import Optional

from src.strats_prob.strategy_def import StrategyDef

logger = logging.getLogger(__name__)

# Module-level registry
_strategies_by_id: dict[int, StrategyDef] = {}
_strategies_by_name: dict[str, StrategyDef] = {}


def register_strategies(strategies: list[StrategyDef]) -> int:
    """Register a list of strategy definitions.

    Args:
        strategies: List of StrategyDef instances to register.

    Returns:
        Number of strategies registered.
    """
    count = 0
    for s in strategies:
        # Detect ID collisions
        if s.id in _strategies_by_id:
            existing = _strategies_by_id[s.id]
            raise ValueError(
                f"Duplicate strategy ID {s.id}: "
                f"new='{s.name}' collides with existing='{existing.name}'"
            )
        # Detect name collisions
        if s.name in _strategies_by_name:
            existing = _strategies_by_name[s.name]
            raise ValueError(
                f"Duplicate strategy name '{s.name}': "
                f"new id={s.id} collides with existing id={existing.id}"
            )
        _strategies_by_id[s.id] = s
        _strategies_by_name[s.name] = s
        count += 1
    logger.info("Registered %d strategies (total: %d)", count, len(_strategies_by_id))
    return count


def get_strategy(strategy_id: int) -> Optional[StrategyDef]:
    """Get a strategy by ID."""
    return _strategies_by_id.get(strategy_id)


def get_strategy_by_name(name: str) -> Optional[StrategyDef]:
    """Get a strategy by name."""
    return _strategies_by_name.get(name)


def get_all_strategies() -> list[StrategyDef]:
    """Get all registered strategies sorted by ID."""
    return sorted(_strategies_by_id.values(), key=lambda s: s.id)


def get_strategies_by_category(category: str) -> list[StrategyDef]:
    """Get all registered strategies of a given category."""
    return sorted(
        [s for s in _strategies_by_id.values() if s.category == category],
        key=lambda s: s.id,
    )


def seed_strategies_to_db(session) -> int:
    """Seed all registered strategies into the probe_strategies DB table.

    Args:
        session: SQLAlchemy session.

    Returns:
        Number of rows affected.
    """
    from src.data.database.probe_repository import ProbeRepository

    repo = ProbeRepository(session)
    db_records = [s.to_db_dict() for s in get_all_strategies()]
    return repo.seed_strategies(db_records)


def clear_registry() -> None:
    """Clear all registered strategies (useful for testing)."""
    _strategies_by_id.clear()
    _strategies_by_name.clear()
