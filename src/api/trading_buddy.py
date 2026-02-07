"""FastAPI router for Trading Buddy endpoints.

Provides API endpoints for:
- Trade intent CRUD (draft, submit, list)
- Trade evaluation
- User account management
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.auth_middleware import get_current_user

from src.data.database.connection import get_db_manager
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
    account_id: int,
) -> DomainTradeIntent:
    """Convert API model to domain model.

    Args:
        data: API request model
        account_id: Authenticated user's account ID

    Returns:
        Domain TradeIntent
    """
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
    logger.debug(
        "Converting intent to response: intent_id=%s, symbol=%s, status=%s",
        intent.intent_id, intent.symbol, intent.status.value,
    )
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


@router.post("/intents", response_model=TradeIntentResponse)
async def create_trade_intent(
    data: TradeIntentCreate,
    user_id: int = Depends(get_current_user),
):
    """Create a new trade intent (draft).

    Creates a trade intent in DRAFT status for later evaluation.
    The intent is validated for basic coherence (stop/target vs entry)
    and persisted to the database.
    """
    logger.debug("create_trade_intent: user_id=%d, symbol=%s", user_id, data.symbol)
    try:
        intent = _create_domain_intent(data, account_id=user_id)

        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            repo = TradingBuddyRepository(session)
            intent_model = repo.create_trade_intent(intent)
            intent.intent_id = intent_model.id

        return _intent_to_response(intent)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_trade_intent(
    request: EvaluateRequest,
    user_id: int = Depends(get_current_user),
):
    """Evaluate a trade intent against all configured evaluators.

    This endpoint:
    1. Creates and persists a trade intent
    2. Loads user-specific risk defaults and rule overrides
    3. Builds market context for the symbol/timeframe
    4. Runs all (or specified) evaluators
    5. Applies guardrails sanitization
    6. Persists the evaluation result
    7. Returns aggregated evaluation with score and findings

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

        # Create domain intent
        intent = _create_domain_intent(
            request.intent,
            account_id=account_id,
        )
        intent.status = TradeIntentStatus.PENDING_EVALUATION

        db_manager = get_db_manager()

        # Persist intent and load user configs in one session
        evaluator_configs = {}
        with db_manager.get_session() as session:
            repo = TradingBuddyRepository(session)

            # Persist the intent
            intent_model = repo.create_trade_intent(intent)
            intent.intent_id = intent_model.id

            # Load user-specific evaluator configs
            evaluator_configs = repo.build_evaluator_configs(account_id)
            logger.debug("Loaded evaluator configs for account %d: %d configs", account_id, len(evaluator_configs))

        # Build context (ensure_fresh_data triggers a messaging request
        # so that the orchestrator fetches any missing bars before we read)
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
                logger.warning(f"Guardrail violation: {warning}")
            result = sanitize_evaluation_result(result)

        # Update intent status
        intent.status = TradeIntentStatus.EVALUATED

        # Persist the evaluation result
        with db_manager.get_session() as session:
            repo = TradingBuddyRepository(session)
            eval_model = repo.save_evaluation(result, intent.intent_id)
            result.evaluation_id = eval_model.id
            repo.update_intent_status(intent.intent_id, TradeIntentStatus.EVALUATED)

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
        logger.exception(f"Evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/intents/{intent_id}")
async def get_trade_intent(intent_id: int):
    """Retrieve a trade intent and its evaluation (if available).

    Args:
        intent_id: ID of the persisted trade intent
    """
    logger.debug("get_trade_intent: intent_id=%d", intent_id)
    try:
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            repo = TradingBuddyRepository(session)

            intent_model = repo.get_trade_intent(intent_id)
            if intent_model is None:
                raise HTTPException(status_code=404, detail=f"Intent {intent_id} not found")

            intent = repo.intent_model_to_domain(intent_model)
            response: dict = {"intent": _intent_to_response(intent)}

            # Include evaluation if one exists
            eval_model = repo.get_evaluation(intent_id)
            if eval_model is not None:
                eval_items = repo.get_evaluation_items(eval_model.id)
                response["evaluation"] = {
                    "evaluation_id": eval_model.id,
                    "score": eval_model.score,
                    "summary": eval_model.summary,
                    "has_blockers": eval_model.blocker_count > 0,
                    "counts": {
                        "blockers": eval_model.blocker_count,
                        "criticals": eval_model.critical_count,
                        "warnings": eval_model.warning_count,
                        "infos": eval_model.info_count,
                    },
                    "evaluators_run": eval_model.evaluators_run,
                    "evaluated_at": eval_model.evaluated_at.isoformat(),
                    "items": [
                        {
                            "evaluator": item.evaluator,
                            "code": item.code,
                            "severity": item.severity,
                            "title": item.title,
                            "message": item.message,
                            "evidence": item.evidence or [],
                        }
                        for item in eval_items
                    ],
                }
            else:
                response["evaluation"] = None

            return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to retrieve intent {intent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evaluators")
async def list_evaluators():
    """List all available evaluators.

    Returns metadata about registered evaluators including
    name, description, and default configuration.
    """
    logger.debug("list_evaluators called")
    from src.evaluators.registry import list_evaluators as _list

    evaluators = _list()
    logger.debug("Returning %d evaluators", len(evaluators))
    return {"evaluators": evaluators}


@router.get("/regime")
async def get_regime_snapshot(
    symbol: str = Query(..., description="Ticker symbol"),
    timeframe: str = Query(..., description="Timeframe (e.g., '5Min', '1Hour')"),
):
    """Get current regime snapshot for a symbol/timeframe.

    Returns regime state, probability, transition risk, entropy,
    and semantic label.
    """
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
        logger.exception(f"Failed to get regime for {symbol}/{timeframe}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/key-levels")
async def get_key_levels(
    symbol: str = Query(..., description="Ticker symbol"),
    timeframe: str = Query(..., description="Primary timeframe"),
):
    """Get current key price levels for a symbol.

    Returns pivot points, prior day HLC, rolling range, and VWAP.
    """
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
        logger.exception(f"Failed to get key levels for {symbol}/{timeframe}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check for Trading Buddy module."""
    return {
        "status": "healthy",
        "module": "trading_buddy",
        "version": "0.1.0",
    }
