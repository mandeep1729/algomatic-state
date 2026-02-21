"""FastAPI router for feature computation endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.auth_middleware import get_current_user
from src.api._data_helpers import (
    compute_features_internal,
    get_features_internal,
    ComputeFeaturesResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["features"])


class FeatureResponse(BaseModel):
    """Feature data response."""
    timestamps: list[str]
    features: dict[str, list[float]]
    feature_names: list[str]


@router.get("/api/features/{symbol}")
async def get_features(
    symbol: str,
    timeframe: str = Query("1Min", description="Bar timeframe"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, description="Max feature rows to return (newest N)"),
    _user_id: int = Depends(get_current_user),
):
    """Compute and return features for the data."""
    try:
        return await get_features_internal(symbol, timeframe, start_date, end_date, limit=limit)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/compute-features/{symbol}")
async def compute_features(
    symbol: str, force: bool = False, _user_id: int = Depends(get_current_user)
):
    """Compute all features for all timeframes of a ticker."""
    try:
        return await compute_features_internal(symbol, force)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error computing features: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
