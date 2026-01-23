"""Data layer for market data ingestion and validation."""

from src.data.cache import DataCache
from src.data.loaders import (
    AlpacaLoader,
    BaseDataLoader,
    CSVLoader,
    DatabaseLoader,
    MultiAssetLoader,
    align_timestamps,
    load_and_combine,
)
from src.data.schemas import OHLCVSchema, validate_ohlcv
from src.data.quality import (
    DataQualityReport,
    DataQualityValidator,
    GapInfo,
    OutlierInfo,
    detect_gaps,
    detect_outliers,
    generate_quality_report,
)
from src.data.database import (
    DatabaseManager,
    get_db_manager,
    Base,
    Ticker,
    OHLCVBar,
    DataSyncLog,
    OHLCVRepository,
)

__all__ = [
    # Loaders
    "AlpacaLoader",
    "BaseDataLoader",
    "CSVLoader",
    "DatabaseLoader",
    "MultiAssetLoader",
    "align_timestamps",
    "load_and_combine",
    # Cache
    "DataCache",
    # Schema validation
    "OHLCVSchema",
    "validate_ohlcv",
    # Quality validation
    "DataQualityReport",
    "DataQualityValidator",
    "GapInfo",
    "OutlierInfo",
    "detect_gaps",
    "detect_outliers",
    "generate_quality_report",
    # Database
    "DatabaseManager",
    "get_db_manager",
    "Base",
    "Ticker",
    "OHLCVBar",
    "DataSyncLog",
    "OHLCVRepository",
]
