"""Artifact versioning and path management for state vector models.

Handles:
- Model artifact paths (scaler, encoder, HMM, metadata)
- State time-series paths (Parquet storage)
- Versioning conventions
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.hmm.contracts import ModelMetadata, VALID_TIMEFRAMES

logger = logging.getLogger(__name__)


# Default root directories
DEFAULT_MODELS_ROOT = Path("models")
DEFAULT_STATES_ROOT = Path("states")


@dataclass
class ArtifactPaths:
    """Paths to all artifacts for a trained model.

    Directory structure:
        models/
          ticker=AAPL/
            timeframe=1Min/
              model_id=state_v003/
                scaler.pkl
                encoder.pkl (or encoder.onnx)
                hmm.pkl
                feature_spec.yaml
                metadata.json
    """

    root: Path
    symbol: str
    timeframe: str
    model_id: str

    def __post_init__(self):
        if self.timeframe not in VALID_TIMEFRAMES:
            raise ValueError(
                f"Invalid timeframe '{self.timeframe}'. "
                f"Valid options: {VALID_TIMEFRAMES}"
            )

    @property
    def model_dir(self) -> Path:
        """Return model directory path."""
        return self.root / f"ticker={self.symbol}" / f"timeframe={self.timeframe}" / f"model_id={self.model_id}"

    @property
    def scaler_path(self) -> Path:
        """Return scaler artifact path."""
        return self.model_dir / "scaler.pkl"

    @property
    def encoder_path(self) -> Path:
        """Return encoder artifact path (pickle)."""
        return self.model_dir / "encoder.pkl"

    @property
    def encoder_onnx_path(self) -> Path:
        """Return encoder ONNX artifact path."""
        return self.model_dir / "encoder.onnx"

    @property
    def hmm_path(self) -> Path:
        """Return HMM artifact path."""
        return self.model_dir / "hmm.pkl"

    @property
    def feature_spec_path(self) -> Path:
        """Return feature spec path."""
        return self.model_dir / "feature_spec.yaml"

    @property
    def metadata_path(self) -> Path:
        """Return metadata JSON path."""
        return self.model_dir / "metadata.json"

    def ensure_dirs(self) -> None:
        """Create model directory if it doesn't exist."""
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def exists(self) -> bool:
        """Check if all required artifacts exist."""
        return (
            self.scaler_path.exists()
            and (self.encoder_path.exists() or self.encoder_onnx_path.exists())
            and self.hmm_path.exists()
            and self.metadata_path.exists()
        )

    def save_metadata(self, metadata: ModelMetadata) -> None:
        """Save metadata to JSON file.

        Args:
            metadata: Model metadata to save
        """
        self.ensure_dirs()
        logger.info(f"Saving metadata to {self.metadata_path}")
        with open(self.metadata_path, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)
        logger.debug(f"Metadata saved: model_id={metadata.model_id}, n_states={metadata.n_states}")

    def load_metadata(self) -> ModelMetadata:
        """Load metadata from JSON file.

        Returns:
            ModelMetadata instance

        Raises:
            FileNotFoundError: If metadata file doesn't exist
        """
        if not self.metadata_path.exists():
            logger.error(f"Metadata not found: {self.metadata_path}")
            raise FileNotFoundError(f"Metadata not found: {self.metadata_path}")

        logger.debug(f"Loading metadata from {self.metadata_path}")
        with open(self.metadata_path) as f:
            data = json.load(f)

        metadata = ModelMetadata.from_dict(data)
        logger.info(f"Loaded metadata: model_id={metadata.model_id}, n_states={metadata.n_states}, features={len(metadata.feature_names)}")
        return metadata


@dataclass
class StatesPaths:
    """Paths for state time-series storage.

    Directory structure:
        states/
          timeframe=1Min/
            model_id=state_v003/
              symbol=AAPL/
                date=2024-01-15/
                  data.parquet
    """

    root: Path
    timeframe: str
    model_id: str

    def __post_init__(self):
        if self.timeframe not in VALID_TIMEFRAMES:
            raise ValueError(
                f"Invalid timeframe '{self.timeframe}'. "
                f"Valid options: {VALID_TIMEFRAMES}"
            )

    @property
    def base_dir(self) -> Path:
        """Return base directory for this model's states."""
        return self.root / f"timeframe={self.timeframe}" / f"model_id={self.model_id}"

    def get_symbol_dir(self, symbol: str) -> Path:
        """Return directory for a specific symbol."""
        return self.base_dir / f"symbol={symbol}"

    def get_date_dir(self, symbol: str, date: datetime) -> Path:
        """Return directory for a specific symbol and date."""
        date_str = date.strftime("%Y-%m-%d")
        return self.get_symbol_dir(symbol) / f"date={date_str}"

    def get_parquet_path(self, symbol: str, date: datetime) -> Path:
        """Return Parquet file path for a specific symbol and date."""
        return self.get_date_dir(symbol, date) / "data.parquet"

    def ensure_dirs(self, symbol: str, date: datetime) -> None:
        """Create directories for symbol/date if they don't exist."""
        self.get_date_dir(symbol, date).mkdir(parents=True, exist_ok=True)

    def list_symbols(self) -> list[str]:
        """List all symbols with stored states."""
        if not self.base_dir.exists():
            return []

        symbols = []
        for path in self.base_dir.iterdir():
            if path.is_dir() and path.name.startswith("symbol="):
                symbol = path.name.replace("symbol=", "")
                symbols.append(symbol)

        return sorted(symbols)

    def list_dates(self, symbol: str) -> list[datetime]:
        """List all dates with stored states for a symbol."""
        symbol_dir = self.get_symbol_dir(symbol)
        if not symbol_dir.exists():
            return []

        dates = []
        for path in symbol_dir.iterdir():
            if path.is_dir() and path.name.startswith("date="):
                date_str = path.name.replace("date=", "")
                dates.append(datetime.strptime(date_str, "%Y-%m-%d"))

        return sorted(dates)


def get_model_path(
    symbol: str,
    timeframe: str,
    model_id: str,
    root: Optional[Path] = None,
) -> ArtifactPaths:
    """Get artifact paths for a model.

    Args:
        symbol: Ticker symbol (e.g., 'AAPL')
        timeframe: Model timeframe
        model_id: Model version identifier
        root: Optional root directory (defaults to 'models/')

    Returns:
        ArtifactPaths instance
    """
    root = root or DEFAULT_MODELS_ROOT
    return ArtifactPaths(root=root, symbol=symbol, timeframe=timeframe, model_id=model_id)


def get_states_path(
    timeframe: str,
    model_id: str,
    root: Optional[Path] = None,
) -> StatesPaths:
    """Get state storage paths for a model.

    Args:
        timeframe: Model timeframe
        model_id: Model version identifier
        root: Optional root directory (defaults to 'states/')

    Returns:
        StatesPaths instance
    """
    root = root or DEFAULT_STATES_ROOT
    return StatesPaths(root=root, timeframe=timeframe, model_id=model_id)


def generate_model_id(prefix: str = "state", version: int = 1) -> str:
    """Generate a model ID with version number.

    Args:
        prefix: Model ID prefix
        version: Version number

    Returns:
        Model ID string (e.g., "state_v001")
    """
    return f"{prefix}_v{version:03d}"


def list_models(
    symbol: str,
    timeframe: str,
    root: Optional[Path] = None,
) -> list[str]:
    """List all model IDs for a symbol and timeframe.

    Args:
        symbol: Ticker symbol (e.g., 'AAPL')
        timeframe: Timeframe to list models for
        root: Optional root directory

    Returns:
        List of model IDs, sorted by version
    """
    root = root or DEFAULT_MODELS_ROOT
    tf_dir = root / f"ticker={symbol}" / f"timeframe={timeframe}"

    if not tf_dir.exists():
        logger.debug(f"No models directory found for {symbol}/{timeframe} at {tf_dir}")
        return []

    model_ids = []
    for path in tf_dir.iterdir():
        if path.is_dir() and path.name.startswith("model_id="):
            model_id = path.name.replace("model_id=", "")
            model_ids.append(model_id)

    logger.debug(f"Found {len(model_ids)} models for {symbol}/{timeframe}: {model_ids}")
    return sorted(model_ids)


def get_latest_model(
    symbol: str,
    timeframe: str,
    root: Optional[Path] = None,
) -> Optional[ArtifactPaths]:
    """Get paths for the latest model version.

    Args:
        symbol: Ticker symbol (e.g., 'AAPL')
        timeframe: Timeframe to get latest model for
        root: Optional root directory

    Returns:
        ArtifactPaths for latest model, or None if no models exist
    """
    model_ids = list_models(symbol, timeframe, root)
    if not model_ids:
        return None

    return get_model_path(symbol, timeframe, model_ids[-1], root)
