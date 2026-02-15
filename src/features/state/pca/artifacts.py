"""Artifact path management for PCA state models."""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_pca_model_path(
    symbol: str,
    timeframe: str,
    model_id: str,
    models_root: Optional[Path] = None,
) -> Path:
    """Get the path to a PCA state model.

    Args:
        symbol: Ticker symbol
        timeframe: Data timeframe
        model_id: Model identifier
        models_root: Root directory for models

    Returns:
        Path to model directory
    """
    if models_root is None:
        models_root = Path("models")

    return models_root / f"ticker={symbol}" / f"timeframe={timeframe}" / f"pca_model_id={model_id}"


def list_pca_models(
    symbol: str,
    timeframe: str,
    models_root: Optional[Path] = None,
) -> list[str]:
    """List available PCA models for a symbol/timeframe.

    Args:
        symbol: Ticker symbol
        timeframe: Data timeframe
        models_root: Root directory for models

    Returns:
        List of model IDs
    """
    if models_root is None:
        models_root = Path("models")

    base_path = models_root / f"ticker={symbol}" / f"timeframe={timeframe}"

    if not base_path.exists():
        logger.debug("PCA models directory does not exist: %s", base_path)
        return []

    model_ids = []
    for path in base_path.iterdir():
        if path.is_dir() and path.name.startswith("pca_model_id="):
            model_id = path.name.replace("pca_model_id=", "")
            # Verify it has required files
            if (path / "metadata.json").exists():
                model_ids.append(model_id)

    return sorted(model_ids)


def get_latest_pca_model(
    symbol: str,
    timeframe: str,
    models_root: Optional[Path] = None,
) -> Optional[str]:
    """Get the latest PCA model ID for a symbol/timeframe.

    Args:
        symbol: Ticker symbol
        timeframe: Data timeframe
        models_root: Root directory for models

    Returns:
        Latest model ID or None if no models exist
    """
    models = list_pca_models(symbol, timeframe, models_root)
    return models[-1] if models else None
