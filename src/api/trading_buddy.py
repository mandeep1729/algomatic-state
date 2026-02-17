"""FastAPI router for Trading Buddy endpoints.

Provides API endpoints for:
- Trade evaluation (in-memory, stateless)
- Evaluator listing
- Market context (regime, key levels)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.auth_middleware import get_current_user

from src.data.database.dependencies import get_trading_repo
from src.data.database.trading_repository import TradingBuddyRepository
from src.trade.intent import (
    TradeDirection,
    TradeIntentStatus,
    TradeIntent as DomainTradeIntent,
)
from src.trade.evaluation import Severity
from src.evaluators.context import ContextPackBuilder
from src.orchestrator import EvaluatorOrchestrator, OrchestratorConfig
from src.rules.guardrails import sanitize_evaluation_result, validate_evaluation_result

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
    timeframe: str = Field(..., description="Setup timeframe (e.g., '1Min', '1Hour')")
    entry_price: float = Field(..., gt=0, description="Planned entry price")
    stop_loss: float = Field(..., gt=0, description="Stop loss price")
    profit_target: float = Field(..., gt=0, description="Profit target price")
    position_size: Optional[float] = Field(None, gt=0, description="Number of shares")
    position_value: Optional[float] = Field(None, gt=0, description="Total position value")
    rationale: Optional[str] = Field(None, description="Trade rationale")


class TradeIntentResponse(BaseModel):
    """Response model for trade intent."""

    symbol: str
    direction: str
    timeframe: str
    entry_price: float
    stop_loss: float
    profit_target: float
    position_size: Optional[float] = None
    position_value: Optional[float] = None
    rationale: Optional[str] = None
    risk_reward_ratio: float
    total_risk: Optional[float] = None


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
    account_id: int,
) -> DomainTradeIntent:
    """Convert API model to domain model."""
    logger.debug(
        "Creating domain intent: symbol=%s, direction=%s, timeframe=%s, account_id=%d",
        data.symbol, data.direction, data.timeframe, account_id,
    )
    return DomainTradeIntent(
        user_id=account_id,
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
        symbol=intent.symbol,
        direction=intent.direction.value,
        timeframe=intent.timeframe,
        entry_price=intent.entry_price,
        stop_loss=intent.stop_loss,
        profit_target=intent.profit_target,
        position_size=intent.position_size,
        position_value=intent.position_value,
        rationale=intent.rationale,
        risk_reward_ratio=intent.risk_reward_ratio,
        total_risk=intent.total_risk,
    )


def _build_evaluation_response(result) -> EvaluationResponse:
    """Convert domain EvaluationResult to API response."""
    logger.debug(
        "Building evaluation response: score=%.2f, has_blockers=%s, items=%d",
        result.score, result.has_blockers, len(result.items),
    )

    def _items_to_response(items):
        return [
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
            for item in items
        ]

    return EvaluationResponse(
        score=result.score,
        summary=result.summary,
        has_blockers=result.has_blockers,
        top_issues=_items_to_response(result.top_issues),
        all_items=_items_to_response(result.items),
        counts={
            "blockers": len(result.blockers),
            "criticals": len(result.criticals),
            "warnings": len(result.warnings),
            "infos": len(result.infos),
        },
        evaluators_run=result.evaluators_run,
        evaluated_at=result.evaluated_at.isoformat(),
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_trade_intent(
    request: EvaluateRequest,
    user_id: int = Depends(get_current_user),
    repo: TradingBuddyRepository = Depends(get_trading_repo),
):
    """Evaluate a trade intent against all configured evaluators.

    This is a stateless evaluation — the intent is not persisted.
    Results are computed in-memory and returned directly.

    The evaluation includes:
    - Overall score (0-100)
    - Summary text
    - Top 3 issues
    - All evaluation items grouped by severity
    """
    logger.debug(
        "evaluate_trade_intent: user_id=%d, symbol=%s, evaluators=%s",
        user_id, request.intent.symbol, request.evaluators,
    )
    try:
        account_id = user_id

        # Create domain intent (in-memory only)
        intent = _create_domain_intent(request.intent, account_id=account_id)
        intent.status = TradeIntentStatus.PENDING_EVALUATION

        # Load user-specific evaluator configs
        evaluator_configs = repo.build_evaluator_configs(account_id)
        logger.debug(
            "Loaded evaluator configs for account %d: %d configs",
            account_id, len(evaluator_configs),
        )

        # Build context
        context_builder = ContextPackBuilder(ensure_fresh_data=True)
        context = context_builder.build(
            symbol=intent.symbol,
            timeframe=intent.timeframe,
            lookback_bars=100,
            additional_timeframes=["1Hour", "1Day"],
        )

        # Configure orchestrator with user-specific configs
        config = OrchestratorConfig(
            context_lookback_bars=100,
            additional_timeframes=["1Hour", "1Day"],
            evaluator_configs=evaluator_configs,
        )
        orchestrator = EvaluatorOrchestrator(config=config)
        orchestrator.load_evaluators(request.evaluators)

        # Run evaluation
        result = orchestrator.evaluate(intent, context)
        logger.debug(
            "Evaluation complete: score=%.2f, items=%d, evaluators=%s",
            result.score, len(result.items), result.evaluators_run,
        )

        # Apply guardrails — sanitize any predictive language
        guardrail_warnings = validate_evaluation_result(result)
        if guardrail_warnings:
            for warning in guardrail_warnings:
                logger.warning("Guardrail violation: %s", warning)
            result = sanitize_evaluation_result(result)

        # Build response
        evaluation_response = _build_evaluation_response(result)

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
                "regimes": {tf: r.to_dict() for tf, r in context.regimes.items()},
                "mtfa": context.mtfa.to_dict() if context.mtfa else None,
            }

        return EvaluateResponse(
            intent=_intent_to_response(intent),
            evaluation=evaluation_response,
            context_summary=context_summary,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Evaluation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evaluators")
async def list_evaluators():
    """List all available evaluators."""
    logger.debug("list_evaluators called")
    from src.evaluators.registry import list_evaluators as _list

    evaluators = _list()
    logger.debug("Returning %d evaluators", len(evaluators))
    return {"evaluators": evaluators}


@router.get("/regime")
async def get_regime_snapshot(
    symbol: str = Query(..., description="Ticker symbol"),
    timeframe: str = Query(..., description="Timeframe (e.g., '1Min', '1Hour')"),
):
    """Get current regime snapshot for a symbol/timeframe."""
    logger.debug("get_regime_snapshot: symbol=%s, timeframe=%s", symbol, timeframe)
    try:
        context_builder = ContextPackBuilder(
            include_features=False,
            include_key_levels=False,
        )
        context = context_builder.build(
            symbol=symbol,
            timeframe=timeframe,
            lookback_bars=10,
        )

        regime = context.regimes.get(timeframe)
        if regime is None:
            raise HTTPException(
                status_code=404,
                detail=f"No regime data available for {symbol}/{timeframe}",
            )

        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "regime": regime.to_dict(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get regime for %s/%s: %s", symbol, timeframe, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/key-levels")
async def get_key_levels(
    symbol: str = Query(..., description="Ticker symbol"),
    timeframe: str = Query(..., description="Primary timeframe"),
):
    """Get current key price levels for a symbol."""
    logger.debug("get_key_levels: symbol=%s, timeframe=%s", symbol, timeframe)
    try:
        context_builder = ContextPackBuilder(
            include_regimes=False,
        )
        context = context_builder.build(
            symbol=symbol,
            timeframe=timeframe,
            lookback_bars=100,
            additional_timeframes=["1Day"],
        )

        if context.key_levels is None:
            raise HTTPException(
                status_code=404,
                detail=f"No key level data available for {symbol}/{timeframe}",
            )

        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "key_levels": context.key_levels.to_dict(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get key levels for %s/%s: %s", symbol, timeframe, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check for Trading Buddy module."""
    return {
        "status": "healthy",
        "module": "trading_buddy",
        "version": "0.2.0",
    }
