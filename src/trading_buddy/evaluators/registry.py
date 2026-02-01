"""Evaluator registry for dynamic discovery and instantiation.

Provides a decorator-based registration system for evaluators,
similar to the feature calculator registry pattern.
"""

import logging
from typing import Optional, Type

from src.trading_buddy.evaluators.base import Evaluator, EvaluatorConfig

logger = logging.getLogger(__name__)

# Global registry of evaluator classes
_EVALUATOR_REGISTRY: dict[str, Type[Evaluator]] = {}


def register_evaluator(name: Optional[str] = None):
    """Decorator to register an evaluator class.

    Usage:
        @register_evaluator("risk_reward")
        class RiskRewardEvaluator(Evaluator):
            ...

    Or with automatic name from class attribute:
        @register_evaluator()
        class RiskRewardEvaluator(Evaluator):
            name = "risk_reward"
            ...

    Args:
        name: Evaluator name (uses class.name if not provided)

    Returns:
        Decorator function
    """
    def decorator(cls: Type[Evaluator]) -> Type[Evaluator]:
        evaluator_name = name or cls.name
        if evaluator_name == "base":
            raise ValueError(
                f"Evaluator {cls.__name__} must define a unique 'name' attribute "
                "or pass name to @register_evaluator()"
            )

        if evaluator_name in _EVALUATOR_REGISTRY:
            logger.warning(
                f"Overwriting existing evaluator '{evaluator_name}' "
                f"with {cls.__name__}"
            )

        _EVALUATOR_REGISTRY[evaluator_name] = cls
        logger.debug(f"Registered evaluator: {evaluator_name} -> {cls.__name__}")
        return cls

    return decorator


def get_evaluator(
    name: str,
    config: Optional[EvaluatorConfig] = None,
) -> Evaluator:
    """Get an evaluator instance by name.

    Args:
        name: Evaluator name
        config: Optional configuration

    Returns:
        Evaluator instance

    Raises:
        KeyError: If evaluator not found
    """
    if name not in _EVALUATOR_REGISTRY:
        available = list(_EVALUATOR_REGISTRY.keys())
        raise KeyError(
            f"Evaluator '{name}' not found. Available: {available}"
        )

    evaluator_cls = _EVALUATOR_REGISTRY[name]
    return evaluator_cls(config=config)


def get_all_evaluators(
    configs: Optional[dict[str, EvaluatorConfig]] = None,
    enabled_only: bool = True,
) -> list[Evaluator]:
    """Get all registered evaluators.

    Args:
        configs: Configuration dict by evaluator name
        enabled_only: Only return enabled evaluators

    Returns:
        List of evaluator instances
    """
    configs = configs or {}
    evaluators = []

    for name, cls in _EVALUATOR_REGISTRY.items():
        config = configs.get(name)
        evaluator = cls(config=config)

        if enabled_only and not evaluator.is_enabled():
            continue

        evaluators.append(evaluator)

    return evaluators


def list_evaluators() -> list[dict]:
    """List all registered evaluators with metadata.

    Returns:
        List of evaluator info dicts
    """
    result = []
    for name, cls in _EVALUATOR_REGISTRY.items():
        result.append({
            "name": name,
            "class": cls.__name__,
            "description": cls.description,
        })
    return result


def clear_registry() -> None:
    """Clear the evaluator registry (mainly for testing)."""
    global _EVALUATOR_REGISTRY
    _EVALUATOR_REGISTRY.clear()
    logger.debug("Cleared evaluator registry")
