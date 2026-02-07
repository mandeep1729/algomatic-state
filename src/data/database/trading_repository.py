"""Repository for Trading Buddy data access.

Provides methods for:
- Loading user accounts and rules
- Persisting trade intents and evaluations
- Converting database models to domain objects
- Trade lifecycle operations (fills, lots, closures, round trips)
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.data.database.trading_buddy_models import (
    UserAccount as UserAccountModel,
    UserProfile as UserProfileModel,
    UserRule as UserRuleModel,
    TradeIntent as TradeIntentModel,
    TradeEvaluation as TradeEvaluationModel,
    TradeEvaluationItem as TradeEvaluationItemModel,
)
from src.data.database.broker_models import TradeFill as TradeFillModel
from src.data.database.trade_lifecycle_models import (
    PositionLot as PositionLotModel,
    LotClosure as LotClosureModel,
    PositionCampaign as PositionCampaignModel,
    CampaignLeg as CampaignLegModel,
    LegFillMap as LegFillMapModel,
    DecisionContext as DecisionContextModel,
)
from src.trade.intent import (
    TradeIntent,
    TradeDirection,
    TradeIntentStatus,
)
from src.trade.evaluation import (
    EvaluationResult,
    EvaluationItem,
    Evidence,
    Severity,
    SEVERITY_PRIORITY,
)
from src.evaluators.base import EvaluatorConfig

logger = logging.getLogger(__name__)


class TradingBuddyRepository:
    """Repository for Trading Buddy data operations.

    Provides methods for loading user configuration and
    persisting trade intents and evaluations.
    """

    def __init__(self, session: Session):
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy session for database operations
        """
        self.session = session

    # -------------------------------------------------------------------------
    # User Account Operations
    # -------------------------------------------------------------------------

    def get_account_by_external_id(self, external_id: str) -> Optional[UserAccountModel]:
        """Get user account by external user ID.

        Args:
            external_id: External user identifier

        Returns:
            UserAccount or None
        """
        return self.session.query(UserAccountModel).filter(
            UserAccountModel.external_user_id == external_id
        ).first()

    def get_account(self, account_id: int) -> Optional[UserAccountModel]:
        """Get user account by ID.

        Args:
            account_id: Account ID

        Returns:
            UserAccount or None
        """
        return self.session.query(UserAccountModel).filter(
            UserAccountModel.id == account_id
        ).first()

    def get_account_by_email(self, email: str) -> Optional[UserAccountModel]:
        """Get user account by email.

        Args:
            email: User email address

        Returns:
            UserAccount or None
        """
        return self.session.query(UserAccountModel).filter(
            UserAccountModel.email == email
        ).first()

    def get_account_by_google_id(self, google_id: str) -> Optional[UserAccountModel]:
        """Get user account by Google ID.

        Args:
            google_id: Google OAuth subject ID

        Returns:
            UserAccount or None
        """
        return self.session.query(UserAccountModel).filter(
            UserAccountModel.google_id == google_id
        ).first()

    def create_account(
        self,
        external_user_id: str,
        name: str,
        email: str,
        google_id: Optional[str] = None,
        auth_provider: str = "google",
        profile_picture_url: Optional[str] = None,
    ) -> UserAccountModel:
        """Create a new user account.

        Args:
            external_user_id: External user identifier
            name: User name
            email: User email
            google_id: Google OAuth subject ID
            auth_provider: Auth provider name
            profile_picture_url: User profile picture URL

        Returns:
            Created UserAccount
        """
        account = UserAccountModel(
            external_user_id=external_user_id,
            name=name,
            email=email,
            google_id=google_id,
            auth_provider=auth_provider,
            profile_picture_url=profile_picture_url,
        )
        self.session.add(account)
        self.session.flush()
        return account

    def get_or_create_account(
        self,
        external_user_id: str,
        name: str,
        email: str,
        **kwargs,
    ) -> UserAccountModel:
        """Get existing account or create a new one.

        Args:
            external_user_id: External user identifier
            name: User name
            email: User email
            **kwargs: Additional account parameters

        Returns:
            UserAccount
        """
        account = self.get_account_by_external_id(external_user_id)
        if account is None:
            account = self.create_account(external_user_id, name, email=email, **kwargs)
        return account

    # -------------------------------------------------------------------------
    # User Profile Operations
    # -------------------------------------------------------------------------

    def get_profile(self, account_id: int) -> Optional[UserProfileModel]:
        """Get user profile by account ID.

        Args:
            account_id: Account ID

        Returns:
            UserProfile or None
        """
        return self.session.query(UserProfileModel).filter(
            UserProfileModel.user_account_id == account_id
        ).first()

    def create_profile(self, account_id: int, **kwargs) -> UserProfileModel:
        """Create a user profile with default risk params.

        Args:
            account_id: Account ID
            **kwargs: Optional overrides for default values

        Returns:
            Created UserProfile
        """
        profile = UserProfileModel(
            user_account_id=account_id,
            account_balance=kwargs.get("account_balance", 0.0),
            max_position_size_pct=kwargs.get("max_position_size_pct", 5.0),
            max_risk_per_trade_pct=kwargs.get("max_risk_per_trade_pct", 1.0),
            max_daily_loss_pct=kwargs.get("max_daily_loss_pct", 3.0),
            min_risk_reward_ratio=kwargs.get("min_risk_reward_ratio", 2.0),
        )
        self.session.add(profile)
        self.session.flush()
        return profile

    def get_or_create_profile(self, account_id: int) -> UserProfileModel:
        """Get existing profile or create one with defaults.

        Args:
            account_id: Account ID

        Returns:
            UserProfile
        """
        profile = self.get_profile(account_id)
        if profile is None:
            profile = self.create_profile(account_id)
        return profile

    def update_profile(self, account_id: int, **kwargs) -> Optional[UserProfileModel]:
        """Update user profile fields.

        Args:
            account_id: Account ID
            **kwargs: Fields to update

        Returns:
            Updated UserProfile or None
        """
        profile = self.get_profile(account_id)
        if profile is None:
            return None

        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        self.session.flush()
        return profile

    # -------------------------------------------------------------------------
    # User Rules Operations
    # -------------------------------------------------------------------------

    def get_user_rules(
        self,
        account_id: int,
        evaluator: Optional[str] = None,
        enabled_only: bool = True,
    ) -> list[UserRuleModel]:
        """Get user rules for an account.

        Args:
            account_id: Account ID
            evaluator: Optional filter by evaluator name
            enabled_only: Only return enabled rules

        Returns:
            List of UserRule
        """
        query = self.session.query(UserRuleModel).filter(
            UserRuleModel.account_id == account_id
        )

        if evaluator:
            query = query.filter(UserRuleModel.evaluator == evaluator)

        if enabled_only:
            query = query.filter(UserRuleModel.is_enabled == True)

        return query.all()

    def create_rule(
        self,
        account_id: int,
        rule_code: str,
        evaluator: str,
        parameters: dict,
        description: Optional[str] = None,
    ) -> UserRuleModel:
        """Create a new user rule.

        Args:
            account_id: Account ID
            rule_code: Rule code
            evaluator: Evaluator name
            parameters: Rule parameters
            description: Rule description

        Returns:
            Created UserRule
        """
        rule = UserRuleModel(
            account_id=account_id,
            rule_code=rule_code,
            evaluator=evaluator,
            parameters=parameters,
            description=description,
        )
        self.session.add(rule)
        self.session.flush()
        return rule

    def build_evaluator_configs(
        self,
        account_id: int,
    ) -> dict[str, EvaluatorConfig]:
        """Build EvaluatorConfig objects from user profile and rules.

        Combines profile-level defaults with rule-specific overrides
        to create configuration for each evaluator.

        Args:
            account_id: Account ID

        Returns:
            Dict mapping evaluator name to EvaluatorConfig
        """
        account = self.get_account(account_id)
        if not account:
            return {}

        profile = self.get_or_create_profile(account_id)
        rules = self.get_user_rules(account_id)

        # Start with profile-level defaults for all evaluators
        base_params = {
            "account_balance": profile.account_balance,
            "max_position_size_pct": profile.max_position_size_pct,
            "max_risk_per_trade_pct": profile.max_risk_per_trade_pct,
            "min_rr_ratio": profile.min_risk_reward_ratio,
        }

        # Group rules by evaluator
        rules_by_evaluator: dict[str, list[UserRuleModel]] = {}
        for rule in rules:
            if rule.evaluator not in rules_by_evaluator:
                rules_by_evaluator[rule.evaluator] = []
            rules_by_evaluator[rule.evaluator].append(rule)

        # Build configs
        configs: dict[str, EvaluatorConfig] = {}

        # For evaluators with rules, merge with base params
        for evaluator_name, evaluator_rules in rules_by_evaluator.items():
            thresholds = {}
            severity_overrides = {}
            custom_params = base_params.copy()

            for rule in evaluator_rules:
                params = rule.parameters or {}

                # Extract thresholds
                if "threshold" in params:
                    thresholds[rule.rule_code] = params["threshold"]
                if "thresholds" in params:
                    thresholds.update(params["thresholds"])

                # Extract severity overrides
                if "severity" in params:
                    severity_overrides[rule.rule_code] = Severity(params["severity"])

                # Extract custom params
                for key, value in params.items():
                    if key not in ("threshold", "thresholds", "severity"):
                        custom_params[key] = value

            configs[evaluator_name] = EvaluatorConfig(
                enabled=True,
                thresholds=thresholds,
                severity_overrides=severity_overrides,
                custom_params=custom_params,
            )

        # For known evaluators without specific rules, use base config
        default_evaluators = ["risk_reward", "exit_plan"]
        for evaluator_name in default_evaluators:
            if evaluator_name not in configs:
                configs[evaluator_name] = EvaluatorConfig(
                    enabled=True,
                    thresholds={},
                    severity_overrides={},
                    custom_params=base_params.copy(),
                )

        return configs

    # -------------------------------------------------------------------------
    # Trade Intent Operations
    # -------------------------------------------------------------------------

    def create_trade_intent(
        self,
        intent: TradeIntent,
    ) -> TradeIntentModel:
        """Persist a trade intent to database.

        Args:
            intent: Domain TradeIntent

        Returns:
            Created TradeIntentModel
        """
        model = TradeIntentModel(
            account_id=intent.account_id or 1,  # Default to 1 if not set
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
            intent_metadata=intent.metadata,
        )
        self.session.add(model)
        self.session.flush()
        return model

    def get_trade_intent(self, intent_id: int) -> Optional[TradeIntentModel]:
        """Get trade intent by ID.

        Args:
            intent_id: Intent ID

        Returns:
            TradeIntentModel or None
        """
        return self.session.query(TradeIntentModel).filter(
            TradeIntentModel.id == intent_id
        ).first()

    def update_intent_status(
        self,
        intent_id: int,
        status: TradeIntentStatus,
    ) -> Optional[TradeIntentModel]:
        """Update trade intent status.

        Args:
            intent_id: Intent ID
            status: New status

        Returns:
            Updated TradeIntentModel or None
        """
        model = self.get_trade_intent(intent_id)
        if model:
            model.status = status.value
            self.session.flush()
        return model

    def intent_model_to_domain(self, model: TradeIntentModel) -> TradeIntent:
        """Convert database model to domain object.

        Args:
            model: TradeIntentModel

        Returns:
            Domain TradeIntent
        """
        return TradeIntent(
            intent_id=model.id,
            user_id=model.account_id,  # Using account_id as user_id
            account_id=model.account_id,
            symbol=model.symbol,
            direction=TradeDirection(model.direction),
            timeframe=model.timeframe,
            entry_price=model.entry_price,
            stop_loss=model.stop_loss,
            profit_target=model.profit_target,
            position_size=model.position_size,
            position_value=model.position_value,
            rationale=model.rationale,
            status=TradeIntentStatus(model.status),
            created_at=model.created_at,
            metadata=model.intent_metadata or {},
        )

    # -------------------------------------------------------------------------
    # Evaluation Operations
    # -------------------------------------------------------------------------

    def save_evaluation(
        self,
        result: EvaluationResult,
        intent_id: int,
    ) -> TradeEvaluationModel:
        """Save evaluation result to database.

        Args:
            result: Domain EvaluationResult
            intent_id: Associated intent ID

        Returns:
            Created TradeEvaluationModel
        """
        # Create evaluation record
        evaluation = TradeEvaluationModel(
            intent_id=intent_id,
            score=result.score,
            summary=result.summary,
            blocker_count=len(result.blockers),
            critical_count=len(result.criticals),
            warning_count=len(result.warnings),
            info_count=len(result.infos),
            evaluators_run=result.evaluators_run,
            evaluated_at=result.evaluated_at,
        )
        self.session.add(evaluation)
        self.session.flush()

        # Create evaluation items
        for item in result.items:
            item_model = TradeEvaluationItemModel(
                evaluation_id=evaluation.id,
                evaluator=item.evaluator,
                code=item.code,
                severity=item.severity.value,
                severity_priority=SEVERITY_PRIORITY[item.severity],
                title=item.title,
                message=item.message,
                evidence=[e.to_dict() for e in item.evidence],
            )
            self.session.add(item_model)

        self.session.flush()
        return evaluation

    def get_evaluation(self, intent_id: int) -> Optional[TradeEvaluationModel]:
        """Get evaluation for an intent.

        Args:
            intent_id: Intent ID

        Returns:
            TradeEvaluationModel or None
        """
        return self.session.query(TradeEvaluationModel).filter(
            TradeEvaluationModel.intent_id == intent_id
        ).first()

    def get_evaluation_items(
        self,
        evaluation_id: int,
    ) -> list[TradeEvaluationItemModel]:
        """Get evaluation items for an evaluation.

        Args:
            evaluation_id: Evaluation ID

        Returns:
            List of TradeEvaluationItemModel
        """
        return self.session.query(TradeEvaluationItemModel).filter(
            TradeEvaluationItemModel.evaluation_id == evaluation_id
        ).order_by(TradeEvaluationItemModel.severity_priority.desc()).all()

    # -------------------------------------------------------------------------
    # Trade Fill Operations
    # -------------------------------------------------------------------------

    def create_trade_fill(self, **kwargs) -> TradeFillModel:
        """Create a trade fill record.

        Args:
            **kwargs: TradeFill column values

        Returns:
            Created TradeFillModel
        """
        fill = TradeFillModel(**kwargs)
        self.session.add(fill)
        self.session.flush()
        logger.info("Created trade fill id=%s symbol=%s side=%s", fill.id, fill.symbol, fill.side)
        return fill

    def get_fills_for_account(
        self,
        account_id: int,
        symbol: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[TradeFillModel]:
        """Get trade fills for an account, optionally filtered.

        Args:
            account_id: Account ID
            symbol: Optional symbol filter
            since: Optional start datetime filter

        Returns:
            List of TradeFillModel ordered by executed_at desc
        """
        query = self.session.query(TradeFillModel).filter(
            TradeFillModel.account_id == account_id
        )
        if symbol:
            query = query.filter(TradeFillModel.symbol == symbol)
        if since:
            query = query.filter(TradeFillModel.executed_at >= since)
        return query.order_by(TradeFillModel.executed_at.desc()).all()

    def get_fill_by_external_id(self, external_trade_id: str) -> Optional[TradeFillModel]:
        """Get a trade fill by its external (broker) trade ID.

        Args:
            external_trade_id: Broker-assigned trade ID

        Returns:
            TradeFillModel or None
        """
        return self.session.query(TradeFillModel).filter(
            TradeFillModel.external_trade_id == external_trade_id
        ).first()

    # -------------------------------------------------------------------------
    # Position Lot Operations
    # -------------------------------------------------------------------------

    def create_lot(self, **kwargs) -> PositionLotModel:
        """Create a position lot.

        Args:
            **kwargs: PositionLot column values

        Returns:
            Created PositionLotModel
        """
        lot = PositionLotModel(**kwargs)
        self.session.add(lot)
        self.session.flush()
        logger.info(
            "Created position lot id=%s symbol=%s direction=%s qty=%s",
            lot.id, lot.symbol, lot.direction, lot.open_qty,
        )
        return lot

    def get_open_lots(
        self,
        account_id: int,
        symbol: str,
    ) -> list[PositionLotModel]:
        """Get open position lots for an account and symbol.

        Args:
            account_id: Account ID
            symbol: Symbol to filter by

        Returns:
            List of open PositionLotModel ordered by opened_at asc (FIFO)
        """
        return self.session.query(PositionLotModel).filter(
            PositionLotModel.account_id == account_id,
            PositionLotModel.symbol == symbol,
            PositionLotModel.status == "open",
        ).order_by(PositionLotModel.opened_at.asc()).all()

    def update_lot_remaining_qty(
        self,
        lot_id: int,
        new_qty: float,
    ) -> Optional[PositionLotModel]:
        """Update the remaining quantity on a lot.

        Automatically sets status to 'closed' if remaining_qty reaches 0.

        Args:
            lot_id: Lot ID
            new_qty: New remaining quantity

        Returns:
            Updated PositionLotModel or None
        """
        lot = self.session.query(PositionLotModel).filter(
            PositionLotModel.id == lot_id
        ).first()
        if not lot:
            logger.warning("Lot id=%s not found for qty update", lot_id)
            return None

        lot.remaining_qty = new_qty
        if new_qty <= 0:
            lot.status = "closed"
            logger.info("Lot id=%s fully closed", lot_id)

        self.session.flush()
        return lot

    def close_lot(self, lot_id: int) -> Optional[PositionLotModel]:
        """Close a position lot by setting remaining_qty=0 and status='closed'.

        Args:
            lot_id: Lot ID

        Returns:
            Closed PositionLotModel or None
        """
        return self.update_lot_remaining_qty(lot_id, 0.0)

    # -------------------------------------------------------------------------
    # Lot Closure Operations
    # -------------------------------------------------------------------------

    def create_closure(self, **kwargs) -> LotClosureModel:
        """Create a lot closure record (open↔close pairing).

        Args:
            **kwargs: LotClosure column values

        Returns:
            Created LotClosureModel
        """
        closure = LotClosureModel(**kwargs)
        self.session.add(closure)
        self.session.flush()
        logger.info(
            "Created lot closure id=%s lot_id=%s qty=%s pnl=%s",
            closure.id, closure.lot_id, closure.matched_qty, closure.realized_pnl,
        )
        return closure

    def get_closures_for_lot(self, lot_id: int) -> list[LotClosureModel]:
        """Get all closures for a given lot.

        Args:
            lot_id: Position lot ID

        Returns:
            List of LotClosureModel ordered by matched_at asc
        """
        return self.session.query(LotClosureModel).filter(
            LotClosureModel.lot_id == lot_id
        ).order_by(LotClosureModel.matched_at.asc()).all()

    # -------------------------------------------------------------------------
    # Position Campaign Operations
    # -------------------------------------------------------------------------

    def create_campaign(self, **kwargs) -> PositionCampaignModel:
        """Create a position campaign record.

        Args:
            **kwargs: PositionCampaign column values

        Returns:
            Created PositionCampaignModel
        """
        campaign = PositionCampaignModel(**kwargs)
        self.session.add(campaign)
        self.session.flush()
        logger.info(
            "Created campaign id=%s symbol=%s direction=%s status=%s",
            campaign.id, campaign.symbol, campaign.direction, campaign.status,
        )
        return campaign

    def get_campaign(self, campaign_id: int) -> Optional[PositionCampaignModel]:
        """Get a campaign by ID.

        Args:
            campaign_id: Campaign ID

        Returns:
            PositionCampaignModel or None
        """
        return self.session.query(PositionCampaignModel).filter(
            PositionCampaignModel.id == campaign_id
        ).first()

    def get_campaigns(
        self,
        account_id: int,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[PositionCampaignModel]:
        """Get campaigns for an account, optionally filtered.

        Args:
            account_id: Account ID
            symbol: Optional symbol filter
            status: Optional status filter ('open' or 'closed')
            limit: Maximum number of results

        Returns:
            List of PositionCampaignModel ordered by created_at desc
        """
        query = self.session.query(PositionCampaignModel).filter(
            PositionCampaignModel.account_id == account_id
        )
        if symbol:
            query = query.filter(PositionCampaignModel.symbol == symbol)
        if status:
            query = query.filter(PositionCampaignModel.status == status)
        return query.order_by(PositionCampaignModel.created_at.desc()).limit(limit).all()

    # -------------------------------------------------------------------------
    # Campaign Leg Operations
    # -------------------------------------------------------------------------

    def create_leg(self, **kwargs) -> CampaignLegModel:
        """Create a campaign leg record.

        Args:
            **kwargs: CampaignLeg column values

        Returns:
            Created CampaignLegModel
        """
        leg = CampaignLegModel(**kwargs)
        self.session.add(leg)
        self.session.flush()
        logger.info(
            "Created leg id=%s campaign_id=%s type=%s side=%s qty=%s",
            leg.id, leg.campaign_id, leg.leg_type, leg.side, leg.quantity,
        )
        return leg

    def get_legs_for_campaign(self, campaign_id: int) -> list[CampaignLegModel]:
        """Get legs for a campaign ordered by started_at.

        Args:
            campaign_id: Campaign ID

        Returns:
            List of CampaignLegModel
        """
        return self.session.query(CampaignLegModel).filter(
            CampaignLegModel.campaign_id == campaign_id
        ).order_by(CampaignLegModel.started_at.asc()).all()

    # -------------------------------------------------------------------------
    # Leg Fill Map Operations
    # -------------------------------------------------------------------------

    def create_leg_fill_map(self, **kwargs) -> LegFillMapModel:
        """Create a leg-fill mapping record.

        Args:
            **kwargs: LegFillMap column values (leg_id, fill_id, allocated_qty)

        Returns:
            Created LegFillMapModel
        """
        mapping = LegFillMapModel(**kwargs)
        self.session.add(mapping)
        self.session.flush()
        return mapping

    # -------------------------------------------------------------------------
    # Decision Context Operations
    # -------------------------------------------------------------------------

    def create_decision_context(self, **kwargs) -> DecisionContextModel:
        """Create a decision context record.

        Args:
            **kwargs: DecisionContext column values

        Returns:
            Created DecisionContextModel
        """
        context = DecisionContextModel(**kwargs)
        self.session.add(context)
        self.session.flush()
        logger.info(
            "Created decision context id=%s type=%s campaign_id=%s",
            context.id, context.context_type, context.campaign_id,
        )
        return context

    def get_contexts_for_campaign(
        self, campaign_id: int
    ) -> list[DecisionContextModel]:
        """Get decision contexts for a campaign.

        Args:
            campaign_id: Campaign ID

        Returns:
            List of DecisionContextModel ordered by created_at
        """
        return self.session.query(DecisionContextModel).filter(
            DecisionContextModel.campaign_id == campaign_id
        ).order_by(DecisionContextModel.created_at.asc()).all()

    def get_context(self, context_id: int) -> Optional[DecisionContextModel]:
        """Get a decision context by ID.

        Args:
            context_id: Context ID

        Returns:
            DecisionContextModel or None
        """
        return self.session.query(DecisionContextModel).filter(
            DecisionContextModel.id == context_id
        ).first()

    # -------------------------------------------------------------------------
    # Campaign Population from Fills
    # -------------------------------------------------------------------------

    def get_processed_fill_ids(self, account_id: int) -> set[int]:
        """Get fill IDs that have already been processed into lots.

        Args:
            account_id: Account ID

        Returns:
            Set of fill IDs that are already in position_lots
        """
        results = self.session.query(PositionLotModel.open_fill_id).filter(
            PositionLotModel.account_id == account_id
        ).all()
        return {r[0] for r in results}

    def get_unprocessed_fills(
        self,
        account_id: int,
        symbol: Optional[str] = None,
    ) -> list[TradeFillModel]:
        """Get trade fills that haven't been processed into lots/campaigns.

        Args:
            account_id: Account ID
            symbol: Optional symbol filter

        Returns:
            List of unprocessed fills ordered by executed_at ascending
        """
        processed_ids = self.get_processed_fill_ids(account_id)

        # Also get fill IDs used in closures
        closure_fill_ids = self.session.query(LotClosureModel.close_fill_id).join(
            PositionLotModel,
            PositionLotModel.id == LotClosureModel.lot_id,
        ).filter(
            PositionLotModel.account_id == account_id
        ).all()
        processed_ids.update(r[0] for r in closure_fill_ids)

        query = self.session.query(TradeFillModel).filter(
            TradeFillModel.account_id == account_id,
        )

        if symbol:
            query = query.filter(TradeFillModel.symbol == symbol)

        if processed_ids:
            query = query.filter(TradeFillModel.id.notin_(processed_ids))

        return query.order_by(TradeFillModel.executed_at.asc()).all()

    def populate_campaigns_from_fills(
        self,
        account_id: int,
        symbol: Optional[str] = None,
    ) -> dict:
        """Build position campaigns from trade fills using FIFO matching.

        Processes fills chronologically:
        - BUY opens/adds to long lots or closes short lots
        - SELL opens/adds to short lots or closes long lots

        When a position returns to flat, a campaign is created to group
        the complete round-trip.

        Args:
            account_id: Account ID to process fills for
            symbol: Optional symbol filter (process single symbol)

        Returns:
            Dict with stats: lots_created, closures_created, campaigns_created
        """
        stats = {
            "lots_created": 0,
            "closures_created": 0,
            "campaigns_created": 0,
            "legs_created": 0,
            "fills_processed": 0,
        }

        # Get all fills for account (both processed and unprocessed)
        # We need all fills to properly track position state
        query = self.session.query(TradeFillModel).filter(
            TradeFillModel.account_id == account_id,
        )
        if symbol:
            query = query.filter(TradeFillModel.symbol == symbol)

        all_fills = query.order_by(TradeFillModel.executed_at.asc()).all()

        if not all_fills:
            logger.info("No fills to process for account_id=%s", account_id)
            return stats

        # Group fills by symbol
        fills_by_symbol: dict[str, list[TradeFillModel]] = {}
        for fill in all_fills:
            if fill.symbol not in fills_by_symbol:
                fills_by_symbol[fill.symbol] = []
            fills_by_symbol[fill.symbol].append(fill)

        # Get already processed fill IDs
        processed_fill_ids = self.get_processed_fill_ids(account_id)

        # Also track fill IDs used in closures
        closure_results = self.session.query(LotClosureModel.close_fill_id).join(
            PositionLotModel,
            PositionLotModel.id == LotClosureModel.lot_id,
        ).filter(
            PositionLotModel.account_id == account_id
        ).all()
        processed_fill_ids.update(r[0] for r in closure_results)

        # Process each symbol
        for sym, fills in fills_by_symbol.items():
            sym_stats = self._process_symbol_fills(
                account_id=account_id,
                symbol=sym,
                fills=fills,
                processed_fill_ids=processed_fill_ids,
            )
            for key in stats:
                stats[key] += sym_stats[key]

        logger.info(
            "Populated campaigns for account_id=%s: %s",
            account_id,
            stats,
        )
        return stats

    def _process_symbol_fills(
        self,
        account_id: int,
        symbol: str,
        fills: list[TradeFillModel],
        processed_fill_ids: set[int],
    ) -> dict:
        """Process fills for a single symbol to create lots/closures/campaigns.

        Args:
            account_id: Account ID
            symbol: Symbol being processed
            fills: List of fills for this symbol, ordered by executed_at
            processed_fill_ids: Set of fill IDs already processed

        Returns:
            Dict with processing stats
        """
        stats = {
            "lots_created": 0,
            "closures_created": 0,
            "campaigns_created": 0,
            "legs_created": 0,
            "fills_processed": 0,
        }

        # Track open lots (FIFO order)
        open_long_lots: list[PositionLotModel] = []
        open_short_lots: list[PositionLotModel] = []

        # Load existing open lots from database
        existing_lots = self.get_open_lots(account_id, symbol)
        for lot in existing_lots:
            if lot.direction == "long":
                open_long_lots.append(lot)
            else:
                open_short_lots.append(lot)

        # Track current campaign in progress (None means flat)
        current_campaign: Optional[PositionCampaignModel] = None
        campaign_lots: list[PositionLotModel] = []
        campaign_closures: list[LotClosureModel] = []

        for fill in fills:
            is_buy = fill.side.lower() == "buy"
            is_new_fill = fill.id not in processed_fill_ids

            if is_buy:
                # BUY: closes short lots first, then opens long
                remaining_qty = fill.quantity

                # Close short lots (FIFO)
                while remaining_qty > 0 and open_short_lots:
                    lot = open_short_lots[0]
                    close_qty = min(remaining_qty, lot.remaining_qty)

                    if is_new_fill:
                        # Calculate P&L for short: (open_price - close_price) * qty
                        pnl = (lot.avg_open_price - fill.price) * close_qty
                        closure = self.create_closure(
                            lot_id=lot.id,
                            open_fill_id=lot.open_fill_id,
                            close_fill_id=fill.id,
                            matched_qty=close_qty,
                            open_price=lot.avg_open_price,
                            close_price=fill.price,
                            realized_pnl=pnl,
                            match_method="fifo",
                        )
                        campaign_closures.append(closure)
                        stats["closures_created"] += 1

                        # Update lot remaining qty
                        new_remaining = lot.remaining_qty - close_qty
                        self.update_lot_remaining_qty(lot.id, new_remaining)
                        lot.remaining_qty = new_remaining

                    remaining_qty -= close_qty

                    if lot.remaining_qty <= 0:
                        open_short_lots.pop(0)

                # Open new long lot with remaining qty
                if remaining_qty > 0 and is_new_fill:
                    # Start a new campaign if we're flat
                    if current_campaign is None:
                        current_campaign = self.create_campaign(
                            account_id=account_id,
                            symbol=symbol,
                            direction="long",
                            opened_at=fill.executed_at,
                            status="open",
                            source="broker_synced",
                        )
                        stats["campaigns_created"] += 1
                        campaign_lots = []
                        campaign_closures = []

                    lot = self.create_lot(
                        account_id=account_id,
                        symbol=symbol,
                        direction="long",
                        opened_at=fill.executed_at,
                        open_fill_id=fill.id,
                        open_qty=remaining_qty,
                        remaining_qty=remaining_qty,
                        avg_open_price=fill.price,
                        campaign_id=current_campaign.id,
                        status="open",
                    )
                    open_long_lots.append(lot)
                    campaign_lots.append(lot)
                    stats["lots_created"] += 1

            else:
                # SELL: closes long lots first, then opens short
                remaining_qty = fill.quantity

                # Close long lots (FIFO)
                while remaining_qty > 0 and open_long_lots:
                    lot = open_long_lots[0]
                    close_qty = min(remaining_qty, lot.remaining_qty)

                    if is_new_fill:
                        # Calculate P&L for long: (close_price - open_price) * qty
                        pnl = (fill.price - lot.avg_open_price) * close_qty
                        closure = self.create_closure(
                            lot_id=lot.id,
                            open_fill_id=lot.open_fill_id,
                            close_fill_id=fill.id,
                            matched_qty=close_qty,
                            open_price=lot.avg_open_price,
                            close_price=fill.price,
                            realized_pnl=pnl,
                            match_method="fifo",
                        )
                        campaign_closures.append(closure)
                        stats["closures_created"] += 1

                        # Update lot remaining qty
                        new_remaining = lot.remaining_qty - close_qty
                        self.update_lot_remaining_qty(lot.id, new_remaining)
                        lot.remaining_qty = new_remaining

                    remaining_qty -= close_qty

                    if lot.remaining_qty <= 0:
                        open_long_lots.pop(0)

                # Open new short lot with remaining qty
                if remaining_qty > 0 and is_new_fill:
                    # Start a new campaign if we're flat
                    if current_campaign is None:
                        current_campaign = self.create_campaign(
                            account_id=account_id,
                            symbol=symbol,
                            direction="short",
                            opened_at=fill.executed_at,
                            status="open",
                            source="broker_synced",
                        )
                        stats["campaigns_created"] += 1
                        campaign_lots = []
                        campaign_closures = []

                    lot = self.create_lot(
                        account_id=account_id,
                        symbol=symbol,
                        direction="short",
                        opened_at=fill.executed_at,
                        open_fill_id=fill.id,
                        open_qty=remaining_qty,
                        remaining_qty=remaining_qty,
                        avg_open_price=fill.price,
                        campaign_id=current_campaign.id,
                        status="open",
                    )
                    open_short_lots.append(lot)
                    campaign_lots.append(lot)
                    stats["lots_created"] += 1

            if is_new_fill:
                stats["fills_processed"] += 1
                processed_fill_ids.add(fill.id)

            # Check if we've returned to flat
            if not open_long_lots and not open_short_lots and current_campaign:
                # Finalize the campaign
                self._finalize_campaign(
                    current_campaign,
                    campaign_lots,
                    campaign_closures,
                    fills,
                )
                stats["legs_created"] += self._create_campaign_legs(
                    current_campaign,
                    fills,
                    campaign_lots,
                    campaign_closures,
                )
                current_campaign = None
                campaign_lots = []
                campaign_closures = []

        return stats

    def _finalize_campaign(
        self,
        campaign: PositionCampaignModel,
        lots: list[PositionLotModel],
        closures: list[LotClosureModel],
        fills: list[TradeFillModel],
    ) -> None:
        """Finalize a campaign by computing aggregated metrics.

        Args:
            campaign: Campaign to finalize
            lots: Lots in this campaign
            closures: Closures in this campaign
            fills: All fills for this symbol (used for timing)
        """
        if not lots:
            return

        # Calculate aggregates
        total_pnl = sum(c.realized_pnl or 0 for c in closures)
        total_qty_opened = sum(lot.open_qty for lot in lots)
        total_qty_closed = sum(c.matched_qty for c in closures)
        num_fills = len(set(lot.open_fill_id for lot in lots)) + len(
            set(c.close_fill_id for c in closures)
        )

        # Calculate average prices
        if lots:
            total_open_value = sum(lot.open_qty * lot.avg_open_price for lot in lots)
            avg_open_price = total_open_value / total_qty_opened if total_qty_opened else 0
        else:
            avg_open_price = None

        if closures:
            total_close_value = sum(c.matched_qty * c.close_price for c in closures)
            avg_close_price = total_close_value / total_qty_closed if total_qty_closed else 0
        else:
            avg_close_price = None

        # Get first open and last close times
        opened_at = min(lot.opened_at for lot in lots)
        if closures:
            # Find close fill times
            close_fill_ids = [c.close_fill_id for c in closures]
            close_fills = [f for f in fills if f.id in close_fill_ids]
            if close_fills:
                closed_at = max(f.executed_at for f in close_fills)
            else:
                closed_at = datetime.utcnow()
        else:
            closed_at = datetime.utcnow()

        # Calculate holding period
        holding_period_sec = int((closed_at - opened_at).total_seconds())

        # Calculate return percentage
        cost_basis = total_qty_opened * (avg_open_price or 0)
        return_pct = (total_pnl / cost_basis * 100) if cost_basis else 0

        # Update campaign
        campaign.opened_at = opened_at
        campaign.closed_at = closed_at
        campaign.qty_opened = total_qty_opened
        campaign.qty_closed = total_qty_closed
        campaign.avg_open_price = avg_open_price
        campaign.avg_close_price = avg_close_price
        campaign.realized_pnl = total_pnl
        campaign.return_pct = return_pct
        campaign.holding_period_sec = holding_period_sec
        campaign.num_fills = num_fills
        campaign.max_qty = total_qty_opened
        campaign.status = "closed"
        campaign.derived_from = {
            "lot_ids": [lot.id for lot in lots],
            "closure_ids": [c.id for c in closures],
        }

        self.session.flush()
        logger.info(
            "Finalized campaign id=%s symbol=%s pnl=%.2f return=%.2f%%",
            campaign.id,
            campaign.symbol,
            total_pnl,
            return_pct,
        )

    def _create_campaign_legs(
        self,
        campaign: PositionCampaignModel,
        fills: list[TradeFillModel],
        lots: list[PositionLotModel],
        closures: list[LotClosureModel],
    ) -> int:
        """Create campaign legs linking to fills.

        Args:
            campaign: Campaign to add legs to
            fills: All fills for this symbol
            lots: Lots in this campaign
            closures: Closures in this campaign

        Returns:
            Number of legs created
        """
        legs_created = 0

        # Create opening leg
        if lots:
            open_fill_ids = [lot.open_fill_id for lot in lots]
            open_fills = [f for f in fills if f.id in open_fill_ids]
            if open_fills:
                first_fill = min(open_fills, key=lambda f: f.executed_at)
                total_open_qty = sum(lot.open_qty for lot in lots)
                avg_price = sum(
                    lot.open_qty * lot.avg_open_price for lot in lots
                ) / total_open_qty

                leg = self.create_leg(
                    campaign_id=campaign.id,
                    leg_type="open",
                    side=first_fill.side.lower(),
                    quantity=total_open_qty,
                    avg_price=avg_price,
                    started_at=first_fill.executed_at,
                    ended_at=max(f.executed_at for f in open_fills),
                    fill_count=len(open_fills),
                )
                legs_created += 1

                # Create fill mappings
                for fill in open_fills:
                    lot_for_fill = next(
                        (lot for lot in lots if lot.open_fill_id == fill.id),
                        None,
                    )
                    qty = lot_for_fill.open_qty if lot_for_fill else fill.quantity
                    self.create_leg_fill_map(
                        leg_id=leg.id,
                        fill_id=fill.id,
                        allocated_qty=qty,
                    )

        # Create closing leg
        if closures:
            close_fill_ids = list(set(c.close_fill_id for c in closures))
            close_fills = [f for f in fills if f.id in close_fill_ids]
            if close_fills:
                first_close = min(close_fills, key=lambda f: f.executed_at)
                total_close_qty = sum(c.matched_qty for c in closures)
                avg_price = sum(
                    c.matched_qty * c.close_price for c in closures
                ) / total_close_qty

                leg = self.create_leg(
                    campaign_id=campaign.id,
                    leg_type="close",
                    side=first_close.side.lower(),
                    quantity=total_close_qty,
                    avg_price=avg_price,
                    started_at=first_close.executed_at,
                    ended_at=max(f.executed_at for f in close_fills),
                    fill_count=len(close_fills),
                )
                legs_created += 1

                # Create fill mappings
                for fill in close_fills:
                    closures_for_fill = [
                        c for c in closures if c.close_fill_id == fill.id
                    ]
                    qty = sum(c.matched_qty for c in closures_for_fill)
                    self.create_leg_fill_map(
                        leg_id=leg.id,
                        fill_id=fill.id,
                        allocated_qty=qty,
                    )

        return legs_created
