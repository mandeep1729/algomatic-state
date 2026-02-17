"""FastAPI router for symbol analysis endpoints (HMM and PCA)."""

import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.auth_middleware import get_current_user
from src.api._data_helpers import (
    compute_features_internal,
    load_ohlcv_internal,
    PROJECT_ROOT,
)
from src.data.database.dependencies import get_market_grpc_client
from src.data.database.models import VALID_TIMEFRAMES
from src.features.state.hmm.artifacts import get_model_path, list_models
from src.features.state.hmm.inference import InferenceEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class AnalyzeResponse(BaseModel):
    """Response for analyze endpoint."""
    symbol: str
    timeframe: str
    features_computed: int
    model_trained: bool
    model_id: Optional[str]
    states_computed: int
    total_bars: int
    message: str


class PCAAnalyzeResponse(BaseModel):
    """Response for PCA analyze endpoint."""
    symbol: str
    timeframe: str
    features_computed: int
    model_trained: bool
    model_id: Optional[str]
    states_computed: int
    n_components: int
    n_states: int
    total_variance_explained: float
    message: str


# ---------------------------------------------------------------------------
# HMM analysis
# ---------------------------------------------------------------------------


@router.post("/api/analyze/{symbol}")
async def analyze_symbol(
    symbol: str,
    timeframe: str = Query("1Min", description="Timeframe to analyze"),
    repo=Depends(get_market_grpc_client),
    _user_id: int = Depends(get_current_user),
):
    """Analyze a symbol: compute features, train model if needed, compute states.

    This endpoint orchestrates:
    1. Compute features for bars that don't have them
    2. Train HMM model if none exists or last training was >30 days ago
    3. Compute states for bars without state entries
    """
    from src.features.state.hmm.training import TrainingPipeline, TrainingConfig
    from src.features.state.hmm.data_pipeline import GapHandler
    from src.features.state.hmm.config import DEFAULT_FEATURE_SET

    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe: {timeframe}. Must be one of {list(VALID_TIMEFRAMES)}"
        )

    symbol = symbol.upper()
    models_root = PROJECT_ROOT / "models"

    result = {
        "symbol": symbol,
        "timeframe": timeframe,
        "features_computed": 0,
        "model_trained": False,
        "model_id": None,
        "states_computed": 0,
        "total_bars": 0,
        "message": "",
    }
    messages = []

    try:
        # Step 0: Ensure OHLCV data is loaded
        logger.info("[Analyze] Step 0: Loading OHLCV data for %s/%s", symbol, timeframe)
        try:
            await load_ohlcv_internal(symbol, timeframe)
            messages.append("OHLCV data loaded")
        except HTTPException as e:
            if e.status_code == 404:
                raise HTTPException(
                    status_code=400,
                    detail=f"No OHLCV data available for {symbol}. Ensure Alpaca API is configured."
                )
            raise

        # Step 1: Compute features
        logger.info("[Analyze] Step 1: Computing features for %s/%s", symbol, timeframe)
        features_result = await compute_features_internal(symbol, force=False)
        result["features_computed"] = features_result.features_stored
        if features_result.features_stored > 0:
            messages.append(f"Computed {features_result.features_stored} features")
        else:
            messages.append("Features already computed")

        # Step 2: Check if model needs training
        logger.info("[Analyze] Step 2: Checking model status for %s %s", symbol, timeframe)
        available_models = list_models(symbol.upper(), timeframe, models_root)
        need_training = True
        current_model_id = None

        if available_models:
            current_model_id = available_models[-1]
            paths = get_model_path(symbol.upper(), timeframe, current_model_id, models_root)
            if paths.exists():
                metadata = paths.load_metadata()
                if metadata.created_at:
                    model_age = datetime.now(timezone.utc) - metadata.created_at
                    if model_age.days < 30:
                        need_training = False
                        result["model_id"] = current_model_id
                        messages.append(f"Model {current_model_id} is current ({model_age.days} days old)")

        if need_training:
            logger.info("[Analyze] Training new model for %s", timeframe)
            ticker = repo.get_ticker(symbol)
            if not ticker:
                raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found")

            features_df = repo.get_features(symbol, timeframe)
            if features_df.empty or len(features_df) < 200:
                logger.warning("Insufficient features for %s: %d bars available, 200 required", symbol, len(features_df))
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient data for training. Need at least 200 bars, have {len(features_df)}"
                )

            available_features = set(features_df.columns)
            feature_names = [f for f in DEFAULT_FEATURE_SET if f in available_features]
            if len(feature_names) < 5:
                raise HTTPException(
                    status_code=400,
                    detail="Insufficient features. Need at least 5 features."
                )

            split_idx = int(len(features_df) * 0.8)
            train_df = features_df.iloc[:split_idx]
            val_df = features_df.iloc[split_idx:]

            gap_handler = GapHandler(timeframe)
            train_df = gap_handler.handle_gaps(train_df)
            val_df = gap_handler.handle_gaps(val_df)

            train_df_clean = train_df[feature_names].dropna()
            val_df_clean = val_df[feature_names].dropna()

            if len(train_df_clean) < 100 or len(val_df_clean) < 20:
                raise HTTPException(
                    status_code=400,
                    detail="Insufficient clean data after NaN removal"
                )

            config = TrainingConfig(
                timeframe=timeframe,
                symbols=[symbol],
                train_start=train_df_clean.index.min(),
                train_end=train_df_clean.index.max(),
                val_start=val_df_clean.index.min(),
                val_end=val_df_clean.index.max(),
                feature_names=feature_names,
                scaler_type="robust",
                encoder_type="pca",
                latent_dim=None,
                n_states=None,
                covariance_type="diag",
                random_seed=42,
            )

            pipeline = TrainingPipeline(models_root=models_root, random_seed=42)
            train_result = pipeline.train(config, train_df_clean, val_df_clean)

            result["model_trained"] = True
            result["model_id"] = train_result.model_id
            current_model_id = train_result.model_id
            messages.append(
                f"Trained new model {train_result.model_id} with {train_result.hmm.n_states} states"
            )

        # Step 3: Compute states
        logger.info("[Analyze] Step 3: Computing states for %s/%s", symbol, timeframe)
        if current_model_id:
            ticker = repo.get_ticker(symbol)

            bars_df = repo.get_bars(symbol, timeframe)
            result["total_bars"] = len(bars_df)

            if bars_df.empty:
                messages.append("No bars to process")
            else:
                existing_states = repo.get_states(symbol, timeframe, current_model_id)
                existing_timestamps = set(existing_states.index) if not existing_states.empty else set()

                all_timestamps = set(bars_df.index)
                missing_timestamps = all_timestamps - existing_timestamps

                if missing_timestamps:
                    features_df = repo.get_features(symbol, timeframe)
                    features_to_process = features_df[features_df.index.isin(missing_timestamps)]

                    if not features_to_process.empty:
                        paths = get_model_path(symbol.upper(), timeframe, current_model_id, models_root)
                        engine = InferenceEngine.from_artifacts(paths)
                        metadata = paths.load_metadata()
                        model_features = metadata.feature_names

                        bar_id_map = repo.get_bar_ids_for_timestamps(
                            ticker.id, timeframe, list(features_to_process.index)
                        )

                        state_records = []
                        engine.reset()

                        for ts, row in features_to_process.iterrows():
                            features = {name: row.get(name, np.nan) for name in model_features}
                            output = engine.process(features, symbol, ts)

                            bar_id = bar_id_map.get(ts)
                            if bar_id:
                                state_records.append({
                                    "bar_id": bar_id,
                                    "state_id": output.state_id,
                                    "state_prob": float(output.state_prob),
                                    "log_likelihood": float(output.log_likelihood)
                                    if not np.isinf(output.log_likelihood) else None,
                                })

                        if state_records:
                            stored = repo.store_states(state_records, current_model_id)
                            result["states_computed"] = stored
                            messages.append(f"Computed {stored} states")
                        else:
                            messages.append("No new states to compute")
                    else:
                        messages.append("No features available for missing bars")
                else:
                    messages.append("All bars already have states")
        else:
            messages.append("No model available for state computation")

        result["message"] = "; ".join(messages)
        logger.info("[Analyze] Complete: %s", result["message"])
        return AnalyzeResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error analyzing %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# PCA analysis
# ---------------------------------------------------------------------------


@router.post("/api/pca/analyze/{symbol}")
async def analyze_symbol_pca(
    symbol: str,
    timeframe: str = Query("1Min", description="Timeframe to analyze"),
    n_components: Optional[int] = Query(None, description="Number of PCA components (auto if not specified)"),
    n_states: Optional[int] = Query(None, description="Number of K-means clusters (auto if not specified)"),
    repo=Depends(get_market_grpc_client),
    _user_id: int = Depends(get_current_user),
):
    """Analyze a symbol using PCA + K-means state computation.

    This endpoint:
    1. Ensures features are computed
    2. Trains a PCA + K-means model
    3. Computes states for all bars
    """
    from src.features.state.pca import (
        PCAStateTrainer,
        PCAStateEngine,
        get_pca_model_path,
        label_pca_states,
        labels_to_dict,
    )

    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe: {timeframe}. Must be one of {list(VALID_TIMEFRAMES)}"
        )

    symbol = symbol.upper()
    models_root = PROJECT_ROOT / "models"

    result = {
        "symbol": symbol,
        "timeframe": timeframe,
        "features_computed": 0,
        "model_trained": False,
        "model_id": None,
        "states_computed": 0,
        "n_components": 0,
        "n_states": 0,
        "total_variance_explained": 0.0,
        "message": "",
    }
    messages = []

    try:
        # Step 0: Ensure OHLCV data is loaded
        logger.info("[PCA Analyze] Step 0: Loading OHLCV data for %s/%s", symbol, timeframe)
        try:
            await load_ohlcv_internal(symbol, timeframe)
            messages.append("OHLCV data loaded")
        except HTTPException as e:
            if e.status_code == 404:
                raise HTTPException(
                    status_code=400,
                    detail=f"No OHLCV data available for {symbol}. Ensure Alpaca API is configured."
                )
            raise

        # Step 1: Ensure features are computed
        logger.info("[PCA Analyze] Step 1: Computing features for %s/%s", symbol, timeframe)
        features_result = await compute_features_internal(symbol, force=False)
        result["features_computed"] = features_result.features_stored
        if features_result.features_stored > 0:
            messages.append(f"Computed {features_result.features_stored} features")
        else:
            messages.append("Features already computed")

        # Step 2: Get features from database
        ticker = repo.get_ticker(symbol)
        if not ticker:
            raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found")

        features_df = repo.get_features(symbol, timeframe)
        if features_df.empty or len(features_df) < 200:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient data for training. Need at least 200 bars, have {len(features_df)}"
            )

        pca_features = [
            "r1", "r5", "r15", "r60",
            "rv_60", "vol_z_60",
            "rsi_14", "macd", "bb_pct",
            "adx_14", "atr_14",
            "relvol_60",
        ]
        available_features = set(features_df.columns)
        feature_names = [f for f in pca_features if f in available_features]

        if len(feature_names) < 5:
            raise HTTPException(
                status_code=400,
                detail="Insufficient features for PCA. Need at least 5 features."
            )

        logger.info("[PCA Analyze] Using %d features: %s", len(feature_names), feature_names)

        # Step 3: Train PCA model
        logger.info("[PCA Analyze] Step 2: Training PCA + K-means model")
        model_id = "pca_v001"

        trainer = PCAStateTrainer(
            n_components=n_components or 6,
            n_states=n_states or 5,
            auto_select_components=n_components is None,
            auto_select_states=n_states is None,
        )

        train_result = trainer.fit(
            df=features_df,
            feature_names=feature_names,
            model_id=model_id,
            timeframe=timeframe,
            symbols=[symbol],
        )

        model_path = get_pca_model_path(symbol, timeframe, model_id, models_root)
        trainer.save(model_path)

        result["model_trained"] = True
        result["model_id"] = model_id
        result["n_components"] = train_result.metadata.n_components
        result["n_states"] = train_result.metadata.n_states
        result["total_variance_explained"] = train_result.metadata.total_variance_explained
        messages.append(
            f"Trained PCA model: {train_result.metadata.n_components} components, "
            f"{train_result.metadata.n_states} states, "
            f"{train_result.metadata.total_variance_explained*100:.1f}% variance explained"
        )

        # Step 4: Compute states and store
        logger.info("[PCA Analyze] Step 3: Computing states")
        engine = PCAStateEngine.from_artifacts(model_path)
        state_df = engine.transform(features_df)

        labels = label_pca_states(engine, features_df, feature_names)
        trainer.metadata.state_mapping = labels_to_dict(labels)
        trainer.save(model_path)

        bar_id_map = repo.get_bar_ids_for_timestamps(
            ticker.id, timeframe, list(features_df.index)
        )

        state_records = []
        for ts, row in state_df.iterrows():
            bar_id = bar_id_map.get(ts)
            if bar_id:
                state_records.append({
                    "bar_id": bar_id,
                    "state_id": int(row["state_id"]),
                    "state_prob": 1.0 - min(row["distance"] / trainer.metadata.ood_threshold, 1.0),
                    "log_likelihood": -float(row["distance"]),
                })

        if state_records:
            stored_count = repo.store_states(state_records, f"pca_{model_id}")
            result["states_computed"] = stored_count
            messages.append(f"Computed {stored_count} states")

        result["message"] = "; ".join(messages)
        logger.info("[PCA Analyze] Complete: %s", result["message"])

        return PCAAnalyzeResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("PCA analysis failed for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail="Internal server error")
