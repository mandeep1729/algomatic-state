"""FastAPI router for Trading Buddy endpoints.

Provides API endpoints for:
- Trade intent CRUD (draft, submit, list)
- Trade evaluation
- User account management
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.data.database.connection import get_db_manager
from src.trading_buddy.domain import (
    TradeDirection,
    TradeIntentStatus,
    TradeIntent as DomainTradeIntent,
    Severity,
)
from src.trading_buddy.context import ContextPackBuilder
from src.trading_buddy.orchestrator import EvaluatorOrchestrator, OrchestratorConfig

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/trading-buddy", tags=["trading-buddy"])


# =============================================================================
# Pydantic Models for API
# =============================================================================


class TradeIntentCreate(BaseModel):
    """Request model for creating a trade intent."""

    symbol: str = Field(..., description="Ticker symbol (e.g., 'AAPL')")
    direction: str = Field(..., description="Trade direction: 'long' or 'short'")
    timeframe: str = Field(..., description="Setup timeframe (e.g., '5Min', '1Hour')")
    entry_price: float = Field(..., gt=0, description="Planned entry price")
    stop_loss: float = Field(..., gt=0, description="Stop loss price")
    profit_target: float = Field(..., gt=0, description="Profit target price")
    position_size: Optional[float] = Field(None, gt=0, description="Number of shares")
    position_value: Optional[float] = Field(None, gt=0, description="Total position value")
    rationale: Optional[str] = Field(None, description="Trade rationale")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "direction": "long",
                "timeframe": "5Min",
                "entry_price": 150.00,
                "stop_loss": 148.50,
                "profit_target": 153.00,
                "position_size": 100,
                "rationale": "Breakout above resistance with volume confirmation",
            }
        }


class TradeIntentResponse(BaseModel):
    """Response model for trade intent."""

    intent_id: Optional[int] = None
    symbol: str
    direction: str
    timeframe: str
    entry_price: float
    stop_loss: float
    profit_target: float
    position_size: Optional[float] = None
    position_value: Optional[float] = None
    rationale: Optional[str] = None
    status: str
    risk_reward_ratio: float
    total_risk: Optional[float] = None
    created_at: str


class EvidenceResponse(BaseModel):
    """Response model for evidence."""

    metric_name: str
    value: float
    threshold: Optional[float] = None
    comparison: Optional[str] = None
    unit: Optional[str] = None


class EvaluationItemResponse(BaseModel):
    """Response model for evaluation item."""

    evaluator: str
    code: str
    severity: str
    title: str
    message: str
    evidence: list[EvidenceResponse] = []


class EvaluationResponse(BaseModel):
    """Response model for evaluation result."""

    score: float
    summary: str
    has_blockers: bool
    top_issues: list[EvaluationItemResponse]
    all_items: list[EvaluationItemResponse]
    counts: dict[str, int]
    evaluators_run: list[str]
    evaluated_at: str


class EvaluateRequest(BaseModel):
    """Request model for evaluation."""

    intent: TradeIntentCreate
    evaluators: Optional[list[str]] = Field(
        None, description="Specific evaluators to run (all if not specified)"
    )
    include_context: bool = Field(
        False, description="Include market context in response"
    )


class EvaluateResponse(BaseModel):
    """Response model for evaluate endpoint."""

    intent: TradeIntentResponse
    evaluation: EvaluationResponse
    context_summary: Optional[dict] = None


# =============================================================================
# Helper Functions
# =============================================================================


def _create_domain_intent(
    data: TradeIntentCreate,
    user_id: int = 1,
    account_id: int = 1,
) -> DomainTradeIntent:
    """Convert API model to domain model.

    Args:
        data: API request model
        user_id: User ID (default for now)
        account_id: Account ID (default for now)

    Returns:
        Domain TradeIntent
    """
    return DomainTradeIntent(
        user_id=user_id,
        account_id=account_id,
        symbol=data.symbol.upper(),
        direction=TradeDirection(data.direction.lower()),
        timeframe=data.timeframe,
        entry_price=data.entry_price,
        stop_loss=data.stop_loss,
        profit_target=data.profit_target,
        position_size=data.position_size,
        position_value=data.position_value,
        rationale=data.rationale,
        status=TradeIntentStatus.DRAFT,
    )


def _intent_to_response(intent: DomainTradeIntent) -> TradeIntentResponse:
    """Convert domain intent to API response."""
    return TradeIntentResponse(
        intent_id=intent.intent_id,
        symbol=intent.symbol,
        direction=intent.direction.value,
        timeframe=intent.timeframe,
        entry_price=intent.entry_price,
        stop_loss=intent.stop_loss,
        profit_target=intent.profit_target,
        position_size=intent.position_size,
        position_value=intent.position_value,
        rationale=intent.rationale,
        status=intent.status.value,
        risk_reward_ratio=intent.risk_reward_ratio,
        total_risk=intent.total_risk,
        created_at=intent.created_at.isoformat(),
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/intents", response_model=TradeIntentResponse)
async def create_trade_intent(data: TradeIntentCreate):
    """Create a new trade intent (draft).

    Creates a trade intent in DRAFT status for later evaluation.
    The intent is validated for basic coherence (stop/target vs entry).
    """
    try:
        intent = _create_domain_intent(data)
        return _intent_to_response(intent)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_trade_intent(request: EvaluateRequest):
    """Evaluate a trade intent against all configured evaluators.

    This endpoint:
    1. Creates a trade intent from the request
    2. Builds market context for the symbol/timeframe
    3. Runs all (or specified) evaluators
    4. Returns aggregated evaluation with score and findings

    The evaluation includes:
    - Overall score (0-100)
    - Summary text
    - Top 3 issues
    - All evaluation items grouped by severity
    """
    try:
        # Create domain intent
        intent = _create_domain_intent(request.intent)
        intent.status = TradeIntentStatus.PENDING_EVALUATION

        # Build context
        context_builder = ContextPackBuilder()
        context = context_builder.build(
            symbol=intent.symbol,
            timeframe=intent.timeframe,
            lookback_bars=100,
            additional_timeframes=["1Hour", "1Day"],
        )

        # Configure orchestrator
        config = OrchestratorConfig(
            context_lookback_bars=100,
            additional_timeframes=["1Hour", "1Day"],
        )
        orchestrator = EvaluatorOrchestrator(config=config)
        orchestrator.load_evaluators(request.evaluators)

        # Run evaluation
        result = orchestrator.evaluate(intent, context)

        # Update intent status
        intent.status = TradeIntentStatus.EVALUATED

        # Build response
        evaluation_response = EvaluationResponse(
            score=result.score,
            summary=result.summary,
            has_blockers=result.has_blockers,
            top_issues=[
                EvaluationItemResponse(
                    evaluator=item.evaluator,
                    code=item.code,
                    severity=item.severity.value,
                    title=item.title,
                    message=item.message,
                    evidence=[
                        EvidenceResponse(
                            metric_name=e.metric_name,
                            value=e.value,
                            threshold=e.threshold,
                            comparison=e.comparison,
                            unit=e.unit,
                        )
                        for e in item.evidence
                    ],
                )
                for item in result.top_issues
            ],
            all_items=[
                EvaluationItemResponse(
                    evaluator=item.evaluator,
                    code=item.code,
                    severity=item.severity.value,
                    title=item.title,
                    message=item.message,
                    evidence=[
                        EvidenceResponse(
                            metric_name=e.metric_name,
                            value=e.value,
                            threshold=e.threshold,
                            comparison=e.comparison,
                            unit=e.unit,
                        )
                        for e in item.evidence
                    ],
                )
                for item in result.items
            ],
            counts={
                "blockers": len(result.blockers),
                "criticals": len(result.criticals),
                "warnings": len(result.warnings),
                "infos": len(result.infos),
            },
            evaluators_run=result.evaluators_run,
            evaluated_at=result.evaluated_at.isoformat(),
        )

        # Build context summary if requested
        context_summary = None
        if request.include_context:
            context_summary = {
                "symbol": context.symbol,
                "primary_timeframe": context.primary_timeframe,
                "current_price": context.current_price,
                "atr": context.atr,
                "has_bars": context.has_bars,
                "has_features": context.has_features,
                "has_regimes": context.has_regimes,
                "key_levels": context.key_levels.to_dict() if context.key_levels else None,
            }

        return EvaluateResponse(
            intent=_intent_to_response(intent),
            evaluation=evaluation_response,
            context_summary=context_summary,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evaluators")
async def list_evaluators():
    """List all available evaluators.

    Returns metadata about registered evaluators including
    name, description, and default configuration.
    """
    from src.trading_buddy.evaluators.registry import list_evaluators as _list

    return {"evaluators": _list()}


@router.get("/health")
async def health_check():
    """Health check for Trading Buddy module."""
    return {
        "status": "healthy",
        "module": "trading_buddy",
        "version": "0.1.0",
    }
