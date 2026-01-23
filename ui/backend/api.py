"""FastAPI backend for regime state visualization UI."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.loaders.csv_loader import CSVLoader
from src.features.pipeline import FeaturePipeline, get_minimal_features
from src.state.windows import WindowGenerator
from src.state.normalization import FeatureNormalizer
from src.state.pca import PCAStateExtractor
from src.state.clustering import RegimeClusterer

app = FastAPI(title="Regime State Visualization API", version="1.0.0")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global data directory
DATA_DIR = Path(__file__).parent.parent.parent / "data"


class DataSourceInfo(BaseModel):
    """Information about available data sources."""
    name: str
    type: str  # "local" or "alpaca"
    path: Optional[str] = None


class OHLCVResponse(BaseModel):
    """OHLCV data response."""
    timestamps: list[str]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]


class FeatureResponse(BaseModel):
    """Feature data response."""
    timestamps: list[str]
    features: dict[str, list[float]]
    feature_names: list[str]


class RegimeResponse(BaseModel):
    """Regime state response."""
    timestamps: list[str]
    regime_labels: list[int]
    regime_info: list[dict]
    transition_matrix: list[list[float]]


class StatisticsResponse(BaseModel):
    """Statistics summary response."""
    ohlcv_stats: dict
    feature_stats: dict
    regime_stats: dict


# Cache for loaded data and computed states
_cache = {}


def get_cached_data(key: str):
    """Get data from cache."""
    return _cache.get(key)


def set_cached_data(key: str, data):
    """Set data in cache."""
    _cache[key] = data


@app.get("/api/sources", response_model=list[DataSourceInfo])
async def get_data_sources():
    """Get list of available data sources."""
    sources = []

    # List local CSV files
    if DATA_DIR.exists():
        for csv_file in DATA_DIR.glob("*.csv"):
            sources.append(DataSourceInfo(
                name=csv_file.stem,
                type="local",
                path=str(csv_file)
            ))

    # Check if Alpaca credentials are available
    if os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"):
        # Add common tickers for Alpaca
        for ticker in ["SPY", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "QQQ", "IWM"]:
            sources.append(DataSourceInfo(
                name=ticker,
                type="alpaca",
                path=None
            ))

    return sources


@app.get("/api/ohlcv/{source_name}")
async def get_ohlcv_data(
    source_name: str,
    source_type: str = Query("local", description="Data source type: local or alpaca"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
):
    """Load OHLCV data from specified source."""
    cache_key = f"ohlcv_{source_type}_{source_name}_{start_date}_{end_date}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    try:
        if source_type == "local":
            loader = CSVLoader(validate=True)
            file_path = DATA_DIR / f"{source_name}.csv"
            if not file_path.exists():
                raise HTTPException(status_code=404, detail=f"File not found: {source_name}.csv")

            start = datetime.fromisoformat(start_date) if start_date else None
            end = datetime.fromisoformat(end_date) if end_date else None
            df = loader.load(file_path, start=start, end=end)

        elif source_type == "alpaca":
            try:
                from src.data.loaders.alpaca_loader import AlpacaLoader
                loader = AlpacaLoader(use_cache=True, validate=True)

                # Default to last 30 days if no dates specified
                end = datetime.fromisoformat(end_date) if end_date else datetime.now()
                start = datetime.fromisoformat(start_date) if start_date else end - timedelta(days=30)

                df = loader.load(source_name, start=start, end=end)
            except ValueError as e:
                raise HTTPException(status_code=401, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=f"Unknown source type: {source_type}")

        if df.empty:
            raise HTTPException(status_code=404, detail="No data found for the specified parameters")

        response = {
            "timestamps": df.index.strftime("%Y-%m-%d %H:%M:%S").tolist(),
            "open": df["open"].tolist(),
            "high": df["high"].tolist(),
            "low": df["low"].tolist(),
            "close": df["close"].tolist(),
            "volume": df["volume"].tolist(),
        }

        # Store raw dataframe in cache for feature computation
        set_cached_data(f"df_{source_type}_{source_name}", df)
        set_cached_data(cache_key, response)

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/features/{source_name}")
async def get_features(
    source_name: str,
    source_type: str = Query("local", description="Data source type"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Compute and return features for the data."""
    # First ensure OHLCV data is loaded
    await get_ohlcv_data(source_name, source_type, start_date, end_date)

    cache_key = f"features_{source_type}_{source_name}_{start_date}_{end_date}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    try:
        df = get_cached_data(f"df_{source_type}_{source_name}")
        if df is None:
            raise HTTPException(status_code=400, detail="OHLCV data not loaded")

        # Compute features
        pipeline = FeaturePipeline.default()
        features_df = pipeline.compute(df)

        # Store for regime computation
        set_cached_data(f"features_df_{source_type}_{source_name}", features_df)

        # Convert to response format
        response = {
            "timestamps": features_df.index.strftime("%Y-%m-%d %H:%M:%S").tolist(),
            "features": {col: features_df[col].replace([np.inf, -np.inf], np.nan).fillna(0).tolist()
                        for col in features_df.columns},
            "feature_names": features_df.columns.tolist(),
        }

        set_cached_data(cache_key, response)
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/regimes/{source_name}")
async def get_regimes(
    source_name: str,
    source_type: str = Query("local"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    n_clusters: int = Query(5, ge=2, le=10),
    window_size: int = Query(60, ge=10, le=200),
    n_components: int = Query(8, ge=2, le=20),
):
    """Compute and return regime states."""
    # Ensure features are computed
    await get_features(source_name, source_type, start_date, end_date)

    cache_key = f"regimes_{source_type}_{source_name}_{start_date}_{end_date}_{n_clusters}_{window_size}_{n_components}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    try:
        features_df = get_cached_data(f"features_df_{source_type}_{source_name}")
        if features_df is None:
            raise HTTPException(status_code=400, detail="Features not computed")

        # Use minimal feature set for regime learning
        minimal_features = get_minimal_features()
        available_features = [f for f in minimal_features if f in features_df.columns]
        feature_subset = features_df[available_features].copy()

        # Fill any NaN values
        feature_subset = feature_subset.fillna(0)

        if len(feature_subset) < window_size:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough data points ({len(feature_subset)}) for window size ({window_size})"
            )

        # Generate windows
        window_gen = WindowGenerator(window_size=window_size, stride=1)
        windows, timestamps = window_gen.generate(feature_subset)

        # Normalize
        normalizer = FeatureNormalizer(method="zscore", clip_value=3.0)
        normalized_windows = normalizer.fit_transform(windows)

        # Extract states with PCA
        pca = PCAStateExtractor(n_components=n_components)
        states = pca.fit_transform(normalized_windows)

        # Compute forward returns for regime labeling
        df = get_cached_data(f"df_{source_type}_{source_name}")
        aligned_df = df.loc[timestamps]
        forward_returns = aligned_df["close"].pct_change(5).shift(-5).fillna(0).values

        # Cluster into regimes
        clusterer = RegimeClusterer(n_clusters=n_clusters, method="kmeans")
        clusterer.fit(states, forward_returns)
        regime_labels = clusterer.predict(states)

        # Get regime info
        regime_summary = clusterer.get_regime_summary()
        transition_matrix = clusterer.transition_matrix.tolist() if clusterer.transition_matrix is not None else []

        response = {
            "timestamps": timestamps.strftime("%Y-%m-%d %H:%M:%S").tolist(),
            "regime_labels": regime_labels.tolist(),
            "regime_info": regime_summary,
            "transition_matrix": transition_matrix,
            "explained_variance": pca.total_explained_variance,
            "n_samples": len(regime_labels),
        }

        set_cached_data(cache_key, response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/statistics/{source_name}")
async def get_statistics(
    source_name: str,
    source_type: str = Query("local"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Get comprehensive statistics summary."""
    # Load data first
    await get_ohlcv_data(source_name, source_type, start_date, end_date)

    try:
        df = get_cached_data(f"df_{source_type}_{source_name}")
        features_df = get_cached_data(f"features_df_{source_type}_{source_name}")

        # OHLCV statistics
        ohlcv_stats = {
            "total_bars": len(df),
            "date_range": {
                "start": df.index.min().strftime("%Y-%m-%d %H:%M:%S"),
                "end": df.index.max().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "price": {
                "min": float(df["low"].min()),
                "max": float(df["high"].max()),
                "mean": float(df["close"].mean()),
                "std": float(df["close"].std()),
                "current": float(df["close"].iloc[-1]),
            },
            "volume": {
                "min": float(df["volume"].min()),
                "max": float(df["volume"].max()),
                "mean": float(df["volume"].mean()),
                "total": float(df["volume"].sum()),
            },
            "returns": {
                "total_return": float((df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100),
                "daily_volatility": float(df["close"].pct_change().std() * 100),
            }
        }

        # Feature statistics
        feature_stats = {}
        if features_df is not None:
            for col in features_df.columns:
                series = features_df[col].replace([np.inf, -np.inf], np.nan).dropna()
                if len(series) > 0:
                    feature_stats[col] = {
                        "min": float(series.min()),
                        "max": float(series.max()),
                        "mean": float(series.mean()),
                        "std": float(series.std()),
                        "median": float(series.median()),
                    }

        # Regime statistics (if computed)
        regime_stats = {}
        regime_cache_key = None
        for key in _cache.keys():
            if key.startswith(f"regimes_{source_type}_{source_name}"):
                regime_cache_key = key
                break

        if regime_cache_key:
            regime_data = get_cached_data(regime_cache_key)
            if regime_data:
                regime_stats = {
                    "n_regimes": len(regime_data.get("regime_info", [])),
                    "regimes": regime_data.get("regime_info", []),
                    "explained_variance": regime_data.get("explained_variance"),
                }

        return {
            "ohlcv_stats": ohlcv_stats,
            "feature_stats": feature_stats,
            "regime_stats": regime_stats,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/cache")
async def clear_cache():
    """Clear the data cache."""
    global _cache
    _cache = {}
    return {"message": "Cache cleared"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
