"""FastAPI router for HMM and PCA regime state endpoints."""

import logging
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.auth_middleware import get_current_user
from src.api._data_helpers import (
    get_cached_data,
    get_features_internal,
    set_cached_data,
    PROJECT_ROOT,
)
from src.data.database.dependencies import get_db
from src.data.database.market_repository import OHLCVRepository
from src.features.state.hmm.artifacts import get_model_path, list_models
from src.features.state.hmm.inference import InferenceEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["regimes"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class StateInfo(BaseModel):
    """Semantic state info."""
    state_id: int
    label: str
    short_label: str
    color: str
    description: str


class RegimeResponse(BaseModel):
    """Regime state response."""
    timestamps: list[str]
    state_ids: list[int]
    state_info: dict[str, StateInfo]


class PCAStateInfo(BaseModel):
    """State info for PCA states response."""
    state_id: int
    label: str
    short_label: str
    color: str
    description: str


class PCARegimeResponse(BaseModel):
    """Response for PCA regimes endpoint."""
    timestamps: list[str]
    state_ids: list[int]
    distances: list[float]
    state_info: dict[str, PCAStateInfo]
    model_id: str
    n_components: int
    n_states: int


# ---------------------------------------------------------------------------
# HMM endpoints
# ---------------------------------------------------------------------------


@router.get("/api/regimes/{symbol}", response_model=RegimeResponse)
async def get_regimes(
    symbol: str,
    timeframe: str = Query("1Min", description="Bar timeframe"),
    model_id: str = Query(None, description="Model ID (default: latest)"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user_id: int = Depends(get_current_user),
):
    """Get HMM regime states for a symbol.

    Loads the trained HMM model and runs inference on cached features
    to return state assignments with semantic labels.
    """
    await get_features_internal(symbol, timeframe, start_date, end_date)

    cache_key = f"regimes_{symbol.upper()}_{timeframe}_{model_id}_{start_date}_{end_date}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    try:
        models_root = PROJECT_ROOT / "models"

        if model_id is None:
            available_models = list_models(symbol.upper(), timeframe, models_root)
            if not available_models:
                raise HTTPException(
                    status_code=404,
                    detail=f"No trained models found for {symbol.upper()} timeframe {timeframe}"
                )
            model_id = available_models[-1]

        paths = get_model_path(symbol.upper(), timeframe, model_id, models_root)

        if not paths.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Model {model_id} not found for {symbol.upper()} timeframe {timeframe}"
            )

        engine = InferenceEngine.from_artifacts(paths)
        metadata = paths.load_metadata()

        features_df = get_cached_data(f"features_df_{symbol.upper()}")
        if features_df is None:
            raise HTTPException(
                status_code=400,
                detail="Features not computed. Load OHLCV data first."
            )

        model_features = metadata.feature_names
        missing_features = set(model_features) - set(features_df.columns)

        if missing_features:
            logger.warning("Missing features for model: %s", missing_features)
            available_model_features = [f for f in model_features if f in features_df.columns]
            if len(available_model_features) < len(model_features) * 0.8:
                raise HTTPException(
                    status_code=400,
                    detail=f"Too many missing features. Model requires: {model_features}"
                )

        repo = OHLCVRepository(db)
        ticker = repo.get_ticker(symbol.upper())
        if ticker:
            bar_id_map = repo.get_bar_ids_for_timestamps(
                ticker.id, timeframe, list(features_df.index)
            )
        else:
            bar_id_map = {}

        timestamps = []
        state_ids = []
        state_records = []

        engine.reset()
        for ts, row in features_df.iterrows():
            features = {name: row.get(name, np.nan) for name in model_features}
            output = engine.process(features, symbol.upper(), ts)
            timestamps.append(ts.strftime("%Y-%m-%dT%H:%M:%SZ"))
            state_ids.append(output.state_id)

            bar_id = bar_id_map.get(ts)
            if bar_id:
                state_records.append({
                    "bar_id": bar_id,
                    "state_id": output.state_id,
                    "state_prob": float(output.state_prob),
                    "log_likelihood": float(output.log_likelihood) if not np.isinf(output.log_likelihood) else None,
                })

        if state_records:
            stored_count = repo.store_states(state_records, model_id)
            db.commit()
            logger.info("Stored %d states for %s/%s/%s", stored_count, symbol.upper(), timeframe, model_id)

        state_info = {}
        if metadata.state_mapping:
            for state_id_str, label_dict in metadata.state_mapping.items():
                state_info[state_id_str] = StateInfo(
                    state_id=label_dict.get("state_id", int(state_id_str)),
                    label=label_dict.get("label", f"state_{state_id_str}"),
                    short_label=label_dict.get("short_label", f"S{state_id_str}"),
                    color=label_dict.get("color", "#6b7280"),
                    description=label_dict.get("description", f"State {state_id_str}"),
                )
        else:
            default_colors = [
                "#22c55e", "#ef4444", "#3b82f6", "#f59e0b",
                "#8b5cf6", "#ec4899", "#14b8a6", "#f97316",
            ]
            for i in range(metadata.n_states):
                state_info[str(i)] = StateInfo(
                    state_id=i,
                    label=f"state_{i}",
                    short_label=f"S{i}",
                    color=default_colors[i % len(default_colors)],
                    description=f"HMM State {i}",
                )

        state_info["-1"] = StateInfo(
            state_id=-1,
            label="unknown",
            short_label="UNK",
            color="#6b7280",
            description="Out-of-distribution observation",
        )

        response = RegimeResponse(
            timestamps=timestamps,
            state_ids=state_ids,
            state_info=state_info,
        )

        set_cached_data(cache_key, response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error computing regimes: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# PCA endpoints
# ---------------------------------------------------------------------------


@router.get("/api/pca/regimes/{symbol}", response_model=PCARegimeResponse)
async def get_pca_regimes(
    symbol: str,
    timeframe: str = Query("1Min", description="Bar timeframe"),
    model_id: str = Query("pca_v001", description="Model ID"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user_id: int = Depends(get_current_user),
):
    """Get PCA-based regime states for a symbol."""
    from src.features.state.pca import PCAStateEngine, get_pca_model_path, list_pca_models

    symbol = symbol.upper()
    models_root = PROJECT_ROOT / "models"

    try:
        available_models = list_pca_models(symbol, timeframe, models_root)
        if not available_models:
            raise HTTPException(
                status_code=404,
                detail=f"No PCA models found for {symbol}/{timeframe}. Run /api/pca/analyze first."
            )

        if model_id not in available_models:
            model_id = available_models[-1]

        model_path = get_pca_model_path(symbol, timeframe, model_id, models_root)
        engine = PCAStateEngine.from_artifacts(model_path)

        repo = OHLCVRepository(db)
        features_df = repo.get_features(symbol, timeframe)

        if features_df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No features found for {symbol}/{timeframe}"
            )

        if start_date:
            features_df = features_df[features_df.index >= start_date]
        if end_date:
            features_df = features_df[features_df.index <= end_date]

        state_df = engine.transform(features_df)

        state_info = {}
        if engine.metadata.state_mapping:
            for state_id_str, label_dict in engine.metadata.state_mapping.items():
                state_info[state_id_str] = PCAStateInfo(
                    state_id=int(state_id_str),
                    label=label_dict.get("label", f"state_{state_id_str}"),
                    short_label=label_dict.get("short_label", f"S{state_id_str}"),
                    color=label_dict.get("color", "#6b7280"),
                    description=label_dict.get("description", f"State {state_id_str}"),
                )
        else:
            default_colors = ["#22c55e", "#ef4444", "#3b82f6", "#f59e0b", "#8b5cf6"]
            for i in range(engine.metadata.n_states):
                state_info[str(i)] = PCAStateInfo(
                    state_id=i,
                    label=f"state_{i}",
                    short_label=f"S{i}",
                    color=default_colors[i % len(default_colors)],
                    description=f"PCA State {i}",
                )

        state_info["-1"] = PCAStateInfo(
            state_id=-1,
            label="unknown",
            short_label="UNK",
            color="#6b7280",
            description="Out-of-distribution observation",
        )

        return PCARegimeResponse(
            timestamps=[ts.strftime("%Y-%m-%dT%H:%M:%SZ") for ts in state_df.index],
            state_ids=state_df["state_id"].tolist(),
            distances=state_df["distance"].tolist(),
            state_info=state_info,
            model_id=model_id,
            n_components=engine.metadata.n_components,
            n_states=engine.metadata.n_states,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get PCA regimes for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail="Internal server error")
