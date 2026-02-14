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

from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified

from src.data.database.trading_buddy_models import (
    UserAccount as UserAccountModel,
    UserProfile as UserProfileModel,
    UserRule as UserRuleModel,
    TradeIntent as TradeIntentModel,
    TradeEvaluation as TradeEvaluationModel,
    TradeEvaluationItem as TradeEvaluationItemModel,
)
from src.data.database.broker_models import TradeFill as TradeFillModel
from src.data.database.strategy_models import Strategy as StrategyModel
from src.data.database.trade_lifecycle_models import (
    PositionLot as PositionLotModel,
    LotClosure as LotClosureModel,
    PositionCampaign as PositionCampaignModel,
    CampaignLeg as CampaignLegModel,
    CampaignCheck as CampaignCheckModel,
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

        Accepts either flat kwargs (account_balance, max_position_size_pct, etc.)
        or structured dicts (profile={...}, risk_profile={...}, site_prefs={...}).

        Args:
            account_id: Account ID
            **kwargs: Optional overrides for default values

        Returns:
            Created UserProfile
        """
        profile_data = dict(UserProfileModel.PROFILE_DEFAULTS)
        risk_data = dict(UserProfileModel.RISK_PROFILE_DEFAULTS)
        site_prefs_data = None

        # Allow passing structured dicts directly
        if "profile" in kwargs:
            profile_data.update(kwargs.pop("profile"))
        if "risk_profile" in kwargs:
            risk_data.update(kwargs.pop("risk_profile"))
        if "site_prefs" in kwargs:
            site_prefs_data = dict(UserProfileModel.SITE_PREF_DEFAULTS)
            site_prefs_data.update(kwargs.pop("site_prefs"))

        # Also support flat kwargs for backward compatibility
        profile_keys = set(UserProfileModel.PROFILE_DEFAULTS.keys())
        risk_keys = set(UserProfileModel.RISK_PROFILE_DEFAULTS.keys())
        site_pref_keys = set(UserProfileModel.SITE_PREF_DEFAULTS.keys())
        for key, value in kwargs.items():
            if key in profile_keys:
                profile_data[key] = value
            elif key in risk_keys:
                risk_data[key] = value
            elif key in site_pref_keys:
                if site_prefs_data is None:
                    site_prefs_data = dict(UserProfileModel.SITE_PREF_DEFAULTS)
                site_prefs_data[key] = value

        profile = UserProfileModel(
            user_account_id=account_id,
            profile=profile_data,
            risk_profile=risk_data,
            site_prefs=site_prefs_data,
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

        Accepts either flat kwargs (account_balance, max_position_size_pct, etc.)
        or structured dicts (profile={...}, risk_profile={...}, site_prefs={...}).

        Args:
            account_id: Account ID
            **kwargs: Fields to update

        Returns:
            Updated UserProfile or None
        """
        existing = self.get_profile(account_id)
        if existing is None:
            return None

        profile_keys = set(UserProfileModel.PROFILE_DEFAULTS.keys())
        risk_keys = set(UserProfileModel.RISK_PROFILE_DEFAULTS.keys())
        site_pref_keys = set(UserProfileModel.SITE_PREF_DEFAULTS.keys())

        # Handle structured dict updates
        # Note: JSONB columns need flag_modified to ensure SQLAlchemy detects changes
        if "profile" in kwargs:
            updated = dict(existing.profile or UserProfileModel.PROFILE_DEFAULTS)
            updated.update(kwargs.pop("profile"))
            existing.profile = updated
            flag_modified(existing, "profile")
        if "risk_profile" in kwargs:
            updated = dict(existing.risk_profile or UserProfileModel.RISK_PROFILE_DEFAULTS)
            updated.update(kwargs.pop("risk_profile"))
            existing.risk_profile = updated
            flag_modified(existing, "risk_profile")
        if "site_prefs" in kwargs:
            updated = dict(existing.site_prefs or UserProfileModel.SITE_PREF_DEFAULTS)
            updated.update(kwargs.pop("site_prefs"))
            existing.site_prefs = updated
            flag_modified(existing, "site_prefs")

        # Handle flat kwargs for backward compatibility
        profile_updates = {}
        risk_updates = {}
        site_pref_updates = {}
        for key, value in kwargs.items():
            if key in profile_keys:
                profile_updates[key] = value
            elif key in risk_keys:
                risk_updates[key] = value
            elif key in site_pref_keys:
                site_pref_updates[key] = value

        if profile_updates:
            updated = dict(existing.profile or UserProfileModel.PROFILE_DEFAULTS)
            updated.update(profile_updates)
            existing.profile = updated
            flag_modified(existing, "profile")

        if risk_updates:
            updated = dict(existing.risk_profile or UserProfileModel.RISK_PROFILE_DEFAULTS)
            updated.update(risk_updates)
            existing.risk_profile = updated
            flag_modified(existing, "risk_profile")

        if site_pref_updates:
            updated = dict(existing.site_prefs or UserProfileModel.SITE_PREF_DEFAULTS)
            updated.update(site_pref_updates)
            existing.site_prefs = updated
            flag_modified(existing, "site_prefs")

        self.session.flush()
        return existing

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
        strategy_id: Optional[int] = None,
    ) -> dict[str, EvaluatorConfig]:
        """Build EvaluatorConfig objects from user profile, rules, and strategy.

        Combines profile-level defaults with strategy-level risk overrides
        and rule-specific overrides to create configuration for each evaluator.

        Override precedence (highest to lowest):
        1. User rules (per-evaluator overrides)
        2. Strategy risk_profile (strategy-level overrides)
        3. User profile risk_profile (account-level defaults)

        Args:
            account_id: Account ID
            strategy_id: Optional strategy ID for risk profile overrides

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

        # Apply strategy-level risk overrides if a strategy is specified
        if strategy_id is not None:
            strategy = self.get_strategy(strategy_id)
            if strategy and strategy.risk_profile:
                logger.info(
                    "Applying strategy risk overrides: strategy_id=%s overrides=%s",
                    strategy_id, strategy.risk_profile,
                )
                # Map strategy risk_profile keys to base_params keys
                key_mapping = {
                    "max_position_size_pct": "max_position_size_pct",
                    "max_risk_per_trade_pct": "max_risk_per_trade_pct",
                    "max_daily_loss_pct": "max_daily_loss_pct",
                    "min_risk_reward_ratio": "min_rr_ratio",
                }
                for risk_key, param_key in key_mapping.items():
                    if risk_key in strategy.risk_profile:
                        base_params[param_key] = strategy.risk_profile[risk_key]

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
    # Strategy Operations
    # -------------------------------------------------------------------------

    def create_strategy(
        self,
        account_id: int,
        name: str,
        description: Optional[str] = None,
        risk_profile: Optional[dict] = None,
    ) -> StrategyModel:
        """Create a new strategy for an account.

        Args:
            account_id: Account ID
            name: Strategy name (unique per account)
            description: Optional description
            risk_profile: Optional risk overrides (e.g., max_position_size_pct)

        Returns:
            Created StrategyModel
        """
        strategy = StrategyModel(
            account_id=account_id,
            name=name,
            description=description,
            risk_profile=risk_profile,
        )
        self.session.add(strategy)
        self.session.flush()
        logger.info(
            "Created strategy id=%s name='%s' account_id=%s risk_profile=%s",
            strategy.id, strategy.name, strategy.account_id, risk_profile,
        )
        return strategy

    def get_strategy(self, strategy_id: int) -> Optional[StrategyModel]:
        """Get a strategy by ID.

        Args:
            strategy_id: Strategy ID

        Returns:
            StrategyModel or None
        """
        return self.session.query(StrategyModel).filter(
            StrategyModel.id == strategy_id
        ).first()

    def get_strategy_by_name(
        self,
        account_id: int,
        name: str,
    ) -> Optional[StrategyModel]:
        """Get a strategy by account and name.

        Args:
            account_id: Account ID
            name: Strategy name

        Returns:
            StrategyModel or None
        """
        return self.session.query(StrategyModel).filter(
            StrategyModel.account_id == account_id,
            StrategyModel.name == name,
        ).first()

    def get_strategies_for_account(
        self,
        account_id: int,
        active_only: bool = True,
    ) -> list[StrategyModel]:
        """Get all strategies for an account.

        Args:
            account_id: Account ID
            active_only: Only return active strategies

        Returns:
            List of StrategyModel ordered by name
        """
        query = self.session.query(StrategyModel).filter(
            StrategyModel.account_id == account_id
        )
        if active_only:
            query = query.filter(StrategyModel.is_active == True)  # noqa: E712
        return query.order_by(StrategyModel.name.asc()).all()

    def update_strategy(
        self,
        strategy_id: int,
        **kwargs,
    ) -> Optional[StrategyModel]:
        """Update strategy fields.

        Args:
            strategy_id: Strategy ID
            **kwargs: Fields to update (name, description, is_active)

        Returns:
            Updated StrategyModel or None
        """
        strategy = self.get_strategy(strategy_id)
        if strategy is None:
            logger.warning("Strategy id=%s not found for update", strategy_id)
            return None

        for key, value in kwargs.items():
            if hasattr(strategy, key):
                setattr(strategy, key, value)

        self.session.flush()
        logger.info("Updated strategy id=%s fields=%s", strategy_id, list(kwargs.keys()))
        return strategy

    def deactivate_strategy(self, strategy_id: int) -> Optional[StrategyModel]:
        """Soft-delete a strategy by setting is_active=False.

        Args:
            strategy_id: Strategy ID

        Returns:
            Deactivated StrategyModel or None
        """
        return self.update_strategy(strategy_id, is_active=False)

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
        query = (
            self.session.query(PositionCampaignModel)
            .options(
                selectinload(PositionCampaignModel.legs)
                .selectinload(CampaignLegModel.fill_maps)
                .selectinload(LegFillMapModel.fill),
            )
            .filter(PositionCampaignModel.account_id == account_id)
        )
        if symbol:
            query = query.filter(PositionCampaignModel.symbol == symbol)
        if status:
            query = query.filter(PositionCampaignModel.status == status)
        return query.order_by(PositionCampaignModel.opened_at.desc()).limit(limit).all()

    # -------------------------------------------------------------------------
    # Campaign Leg Operations
    # -------------------------------------------------------------------------

    def create_leg(self, **kwargs) -> CampaignLegModel:
        """Create a campaign leg record.

        Behavioral checks are now handled asynchronously by the
        ReviewerOrchestrator via REVIEW_* events.

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
    # Campaign Check Operations
    # -------------------------------------------------------------------------

    def create_campaign_check(
        self,
        leg_id: int,
        account_id: int,
        check_type: str,
        severity: str,
        passed: bool,
        check_phase: str,
        details: Optional[dict] = None,
        nudge_text: Optional[str] = None,
    ) -> CampaignCheckModel:
        """Create a campaign check record.

        Args:
            leg_id: Campaign leg ID
            account_id: Account ID
            check_type: Check category (e.g. "risk_sanity")
            severity: "info", "warn", or "block"
            passed: Whether the check passed
            check_phase: When the check applies
            details: Structured metrics (JSONB)
            nudge_text: Human-readable nudge message

        Returns:
            Created CampaignCheckModel
        """
        check = CampaignCheckModel(
            leg_id=leg_id,
            account_id=account_id,
            check_type=check_type,
            severity=severity,
            passed=passed,
            details=details,
            nudge_text=nudge_text,
            check_phase=check_phase,
            checked_at=datetime.utcnow(),
        )
        self.session.add(check)
        self.session.flush()
        logger.info(
            "Created campaign check id=%s leg_id=%s type=%s severity=%s passed=%s",
            check.id, leg_id, check_type, severity, passed,
        )
        return check

    def get_checks_for_leg(self, leg_id: int) -> list[CampaignCheckModel]:
        """Get all checks for a campaign leg.

        Args:
            leg_id: Campaign leg ID

        Returns:
            List of CampaignCheckModel ordered by checked_at
        """
        return self.session.query(CampaignCheckModel).filter(
            CampaignCheckModel.leg_id == leg_id
        ).order_by(CampaignCheckModel.checked_at.asc()).all()

    def acknowledge_check(
        self,
        check_id: int,
        trader_action: str,
    ) -> Optional[CampaignCheckModel]:
        """Acknowledge a check and record the trader's action.

        Args:
            check_id: Campaign check ID
            trader_action: One of "proceeded", "modified", "cancelled"

        Returns:
            Updated CampaignCheckModel or None
        """
        check = self.session.query(CampaignCheckModel).filter(
            CampaignCheckModel.id == check_id
        ).first()

        if check is None:
            logger.warning("Check id=%s not found for acknowledgement", check_id)
            return None

        check.acknowledged = True
        check.trader_action = trader_action
        self.session.flush()
        logger.info(
            "Acknowledged check id=%s action=%s", check_id, trader_action,
        )
        return check

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

        # Restore current_campaign from existing open lots so new fills
        # join the existing campaign instead of creating a duplicate.
        if open_long_lots or open_short_lots:
            active_lots = open_long_lots or open_short_lots
            for lot in active_lots:
                if lot.campaign_id:
                    existing = self.session.get(PositionCampaignModel, lot.campaign_id)
                    if existing and existing.status == "open":
                        current_campaign = existing
                        campaign_lots = list(active_lots)
                        logger.debug(
                            "Restored current_campaign id=%s for %s from existing open lots",
                            existing.id,
                            symbol,
                        )
                        break

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
                leg_stats = self.populate_legs_from_campaigns(current_campaign.id)
                stats["legs_created"] += leg_stats["legs_created"]
                current_campaign = None
                campaign_lots = []
                campaign_closures = []

        # Handle still-open campaign: create legs for positions not yet closed
        if current_campaign and campaign_lots:
            leg_stats = self.populate_legs_from_campaigns(current_campaign.id)
            stats["legs_created"] += leg_stats["legs_created"]
            if leg_stats["legs_created"]:
                logger.info(
                    "Created legs for open campaign id=%s symbol=%s",
                    current_campaign.id,
                    symbol,
                )

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

    # -------------------------------------------------------------------------
    # Campaign Leg Population with Semantic Leg Types
    # -------------------------------------------------------------------------

    def populate_legs_from_campaigns(self, campaign_id: int) -> dict:
        """Populate CampaignLeg records from a campaign's fills.

        Creates legs with semantic leg_type based on position direction transitions:
        - open: First entry into a position (from flat)
        - add: Adding to an existing position (scale-in)
        - reduce: Partially reducing a position (scale-out)
        - close: Fully closing a position (back to flat)
        - flip_close: Closing a position as part of a direction flip
        - flip_open: Opening a new position after a flip

        Args:
            campaign_id: The campaign to populate legs for

        Returns:
            Dict with stats: legs_created, fill_maps_created
        """
        stats = {
            "legs_created": 0,
            "fill_maps_created": 0,
        }

        campaign = self.get_campaign(campaign_id)
        if not campaign:
            logger.warning("Campaign id=%s not found for leg population", campaign_id)
            return stats

        # Get lots and closures for this campaign
        lots = self.session.query(PositionLotModel).filter(
            PositionLotModel.campaign_id == campaign_id
        ).all()

        closures = []
        for lot in lots:
            lot_closures = self.get_closures_for_lot(lot.id)
            closures.extend(lot_closures)

        if not lots and not closures:
            logger.info("No lots or closures for campaign id=%s", campaign_id)
            return stats

        # Gather all relevant fill IDs
        fill_ids = set()
        for lot in lots:
            fill_ids.add(lot.open_fill_id)
        for closure in closures:
            fill_ids.add(closure.close_fill_id)

        if not fill_ids:
            return stats

        # Get fills and sort chronologically
        fills = self.session.query(TradeFillModel).filter(
            TradeFillModel.id.in_(fill_ids)
        ).order_by(TradeFillModel.executed_at.asc()).all()

        if not fills:
            return stats

        # Build lookup maps for efficient access
        lot_by_open_fill: dict[int, PositionLotModel] = {
            lot.open_fill_id: lot for lot in lots
        }
        closures_by_close_fill: dict[int, list[LotClosureModel]] = {}
        for closure in closures:
            if closure.close_fill_id not in closures_by_close_fill:
                closures_by_close_fill[closure.close_fill_id] = []
            closures_by_close_fill[closure.close_fill_id].append(closure)

        # Skip if campaign already has legs (non-destructive)
        existing_legs = self.get_legs_for_campaign(campaign_id)
        if existing_legs:
            logger.info(
                "Campaign %s already has %d legs, skipping",
                campaign_id, len(existing_legs),
            )
            return stats

        # Process fills and create legs with semantic types
        legs_data = self._compute_leg_types(
            fills=fills,
            lot_by_open_fill=lot_by_open_fill,
            closures_by_close_fill=closures_by_close_fill,
            campaign_direction=campaign.direction,
        )

        # Create leg records and fill maps
        for leg_data in legs_data:
            leg = self.create_leg(
                campaign_id=campaign_id,
                symbol=campaign.symbol,
                direction=campaign.direction,
                account_id=campaign.account_id,
                leg_type=leg_data["leg_type"],
                side=leg_data["side"],
                quantity=leg_data["quantity"],
                avg_price=leg_data["avg_price"],
                started_at=leg_data["started_at"],
                ended_at=leg_data["ended_at"],
                fill_count=leg_data["fill_count"],
            )
            stats["legs_created"] += 1

            # Create fill mappings
            for fill_id, allocated_qty in leg_data["fill_allocations"]:
                self.create_leg_fill_map(
                    leg_id=leg.id,
                    fill_id=fill_id,
                    allocated_qty=allocated_qty,
                )
                stats["fill_maps_created"] += 1

        logger.info(
            "Populated legs for campaign id=%s: %s",
            campaign_id,
            stats,
        )
        return stats

    def _compute_leg_types(
        self,
        fills: list[TradeFillModel],
        lot_by_open_fill: dict[int, PositionLotModel],
        closures_by_close_fill: dict[int, list[LotClosureModel]],
        campaign_direction: str,
    ) -> list[dict]:
        """Compute semantic leg types based on position state transitions.

        Processes fills chronologically and tracks position state to determine
        the appropriate leg_type for each fill or group of fills.

        Args:
            fills: Fills sorted by executed_at ascending
            lot_by_open_fill: Map of open_fill_id to PositionLot
            closures_by_close_fill: Map of close_fill_id to list of LotClosure
            campaign_direction: Campaign direction ('long' or 'short')

        Returns:
            List of leg data dicts with keys:
            - leg_type, side, quantity, avg_price, started_at, ended_at,
              fill_count, fill_allocations (list of (fill_id, qty) tuples)
        """
        legs_data = []

        # Track current position state
        # position > 0 means long, position < 0 means short, position == 0 means flat
        position = 0.0

        for fill in fills:
            is_buy = fill.side.lower() == "buy"
            fill_side = "buy" if is_buy else "sell"

            # Determine if this fill opens or closes position
            is_opening_fill = fill.id in lot_by_open_fill
            is_closing_fill = fill.id in closures_by_close_fill

            # Calculate position change from this fill
            if is_opening_fill:
                lot = lot_by_open_fill[fill.id]
                open_qty = lot.open_qty
                # Open fills increase position in the campaign direction
                if campaign_direction == "long":
                    qty_change = open_qty
                else:
                    qty_change = -open_qty
            elif is_closing_fill:
                close_closures = closures_by_close_fill[fill.id]
                close_qty = sum(c.matched_qty for c in close_closures)
                # Close fills decrease position toward flat
                if campaign_direction == "long":
                    qty_change = -close_qty
                else:
                    qty_change = close_qty
            else:
                # Fill not associated with lots or closures, skip
                continue

            # Determine leg_type based on position state transition
            prev_position = position
            new_position = position + qty_change

            leg_type = self._determine_leg_type(
                prev_position=prev_position,
                new_position=new_position,
                is_buy=is_buy,
                campaign_direction=campaign_direction,
            )

            # Calculate fill quantity and price for this leg
            if is_opening_fill:
                lot = lot_by_open_fill[fill.id]
                quantity = lot.open_qty
                avg_price = lot.avg_open_price
                fill_allocations = [(fill.id, quantity)]
            else:
                close_closures = closures_by_close_fill[fill.id]
                quantity = sum(c.matched_qty for c in close_closures)
                total_value = sum(c.matched_qty * c.close_price for c in close_closures)
                avg_price = total_value / quantity if quantity > 0 else 0
                fill_allocations = [(fill.id, quantity)]

            # Create leg data
            leg_data = {
                "leg_type": leg_type,
                "side": fill_side,
                "quantity": quantity,
                "avg_price": avg_price,
                "started_at": fill.executed_at,
                "ended_at": fill.executed_at,
                "fill_count": 1,
                "fill_allocations": fill_allocations,
            }
            legs_data.append(leg_data)

            # Update position state
            position = new_position

        return legs_data

    def populate_campaigns_and_legs(
        self,
        account_id: int,
        symbol: Optional[str] = None,
    ) -> dict:
        """Orchestrator method to build complete trading journal from fills.

        Calls populate_campaigns_from_fills to create campaigns and lots,
        then calculates total P&L across all created campaigns.

        Args:
            account_id: Account ID to process fills for
            symbol: Optional symbol filter (process single symbol)

        Returns:
            Dict with stats: campaigns_created, lots_created, closures_created,
            legs_created, fills_processed, total_pnl, leg_ids
        """
        # Run the main population logic
        stats = self.populate_campaigns_from_fills(account_id=account_id, symbol=symbol)

        # Track all leg IDs created during population
        created_leg_ids: list[int] = []

        # Backfill legs for any campaigns that have zero legs
        campaigns = self.get_campaigns(account_id, symbol=symbol, limit=1000)
        for campaign in campaigns:
            existing_legs = self.get_legs_for_campaign(campaign.id)
            if not existing_legs:
                backfill_stats = self.populate_legs_from_campaigns(campaign.id)
                stats["legs_created"] += backfill_stats.get("legs_created", 0)
                if backfill_stats.get("legs_created", 0) > 0:
                    # Collect IDs of newly created legs
                    new_legs = self.get_legs_for_campaign(campaign.id)
                    created_leg_ids.extend(leg.id for leg in new_legs)
                    logger.info(
                        "Backfilled %d legs for campaign id=%s (%s)",
                        backfill_stats["legs_created"],
                        campaign.id,
                        campaign.symbol,
                    )

        # Calculate total P&L from all campaigns
        total_pnl = sum(c.realized_pnl or 0.0 for c in campaigns if c.status == "closed")

        stats["total_pnl"] = total_pnl
        stats["leg_ids"] = created_leg_ids

        logger.info(
            "Populated campaigns and legs for account_id=%s: "
            "campaigns=%d, lots=%d, legs=%d, pnl=%.2f",
            account_id,
            stats["campaigns_created"],
            stats["lots_created"],
            stats["legs_created"],
            total_pnl,
        )

        return stats

    def _determine_leg_type(
        self,
        prev_position: float,
        new_position: float,
        is_buy: bool,
        campaign_direction: str,
    ) -> str:
        """Determine the semantic leg type based on position state transition.

        Args:
            prev_position: Position before the fill (positive=long, negative=short)
            new_position: Position after the fill
            is_buy: True if the fill is a buy
            campaign_direction: Campaign direction ('long' or 'short')

        Returns:
            One of: 'open', 'add', 'reduce', 'close', 'flip_close', 'flip_open'
        """
        was_flat = abs(prev_position) < 0.0001
        is_flat = abs(new_position) < 0.0001
        was_long = prev_position > 0.0001
        was_short = prev_position < -0.0001
        is_long = new_position > 0.0001
        is_short = new_position < -0.0001

        # Check for direction flip (crossing zero and going to opposite side)
        crossed_zero = (was_long and is_short) or (was_short and is_long)

        if crossed_zero:
            # This is a flip scenario - would require flip_close followed by flip_open
            # For simplicity, we'll assign based on the dominant action
            if is_buy:
                if was_short:
                    # Buy while short -> closing short (flip_close) or going long
                    if is_flat:
                        return "close"
                    elif is_long:
                        return "flip_open"
                    else:
                        return "reduce"
            else:
                if was_long:
                    # Sell while long -> closing long (flip_close) or going short
                    if is_flat:
                        return "close"
                    elif is_short:
                        return "flip_open"
                    else:
                        return "reduce"

        # From flat -> position = 'open'
        if was_flat and not is_flat:
            return "open"

        # From position -> flat = 'close'
        if not was_flat and is_flat:
            return "close"

        # Adding to position (same direction, increasing magnitude)
        if was_long and is_long and new_position > prev_position:
            return "add"
        if was_short and is_short and new_position < prev_position:
            return "add"

        # Reducing position (same direction, decreasing magnitude)
        if was_long and is_long and new_position < prev_position:
            return "reduce"
        if was_short and is_short and new_position > prev_position:
            return "reduce"

        # Default fallback
        if was_flat:
            return "open"
        elif is_flat:
            return "close"
        else:
            # Continuing in same direction
            if abs(new_position) > abs(prev_position):
                return "add"
            else:
                return "reduce"

    # =========================================================================
    # Campaign Orphan Support
    # =========================================================================

    def delete_campaign(self, campaign_id: int, account_id: int) -> dict:
        """Delete a campaign, orphaning its legs instead of destroying them.

        Steps:
        1. Verify campaign ownership
        2. Clear strategy_id on DecisionContexts for legs in this campaign
        3. Set campaign_id=NULL on legs (orphan them)
        4. Set campaign_id=NULL on DecisionContexts linked to this campaign
        5. Set campaign_id=NULL on PositionLots linked to this campaign
        6. Set campaign_id=NULL on TradeEvaluations linked to this campaign
        7. Delete the campaign record

        Args:
            campaign_id: Campaign to delete
            account_id: Account ID for ownership verification

        Returns:
            Dict with legs_orphaned and contexts_updated counts

        Raises:
            ValueError: If campaign not found or not owned by account
        """
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")
        if campaign.account_id != account_id:
            raise ValueError(f"Campaign {campaign_id} not owned by account {account_id}")

        # Get legs for this campaign
        legs = self.get_legs_for_campaign(campaign_id)
        leg_ids = [leg.id for leg in legs]

        # Clear strategy_id on DecisionContexts for these legs
        contexts_updated = 0
        if leg_ids:
            contexts_updated = (
                self.session.query(DecisionContextModel)
                .filter(DecisionContextModel.leg_id.in_(leg_ids))
                .update(
                    {DecisionContextModel.strategy_id: None},
                    synchronize_session="fetch",
                )
            )
            logger.info(
                "Cleared strategy_id on %d contexts for campaign %s legs",
                contexts_updated, campaign_id,
            )

        # Orphan legs (set campaign_id=NULL)
        legs_orphaned = (
            self.session.query(CampaignLegModel)
            .filter(CampaignLegModel.campaign_id == campaign_id)
            .update(
                {CampaignLegModel.campaign_id: None},
                synchronize_session="fetch",
            )
        )

        # Unlink DecisionContexts from this campaign
        self.session.query(DecisionContextModel).filter(
            DecisionContextModel.campaign_id == campaign_id,
        ).update(
            {DecisionContextModel.campaign_id: None},
            synchronize_session="fetch",
        )

        # Unlink PositionLots from this campaign
        self.session.query(PositionLotModel).filter(
            PositionLotModel.campaign_id == campaign_id,
        ).update(
            {PositionLotModel.campaign_id: None},
            synchronize_session="fetch",
        )

        # Unlink TradeEvaluations from this campaign
        self.session.query(TradeEvaluationModel).filter(
            TradeEvaluationModel.campaign_id == campaign_id,
        ).update(
            {TradeEvaluationModel.campaign_id: None},
            synchronize_session="fetch",
        )

        # Delete the campaign
        self.session.delete(campaign)
        self.session.flush()

        logger.info(
            "Deleted campaign %s: orphaned %d legs, updated %d contexts",
            campaign_id, legs_orphaned, contexts_updated,
        )

        return {"legs_orphaned": legs_orphaned, "contexts_updated": contexts_updated}

    def consolidate_campaigns(
        self, account_id: int, symbol: Optional[str] = None
    ) -> dict:
        """Merge duplicate open campaigns for the same (account, symbol, direction).

        When incremental sync creates parallel open campaigns for the same
        position, this method consolidates them by keeping the oldest campaign
        and reassigning all related objects from the duplicates.

        Args:
            account_id: Account ID to consolidate for
            symbol: Optional symbol filter (consolidate all symbols if None)

        Returns:
            Dict with stats: groups_merged, campaigns_removed,
            lots_reassigned, legs_reassigned
        """
        from sqlalchemy import func as sa_func

        stats = {
            "groups_merged": 0,
            "campaigns_removed": 0,
            "lots_reassigned": 0,
            "legs_reassigned": 0,
        }

        # Find (symbol, direction) groups with >1 open campaign
        query = (
            self.session.query(
                PositionCampaignModel.symbol,
                PositionCampaignModel.direction,
                sa_func.count(PositionCampaignModel.id).label("cnt"),
            )
            .filter(
                PositionCampaignModel.account_id == account_id,
                PositionCampaignModel.status == "open",
            )
            .group_by(
                PositionCampaignModel.symbol,
                PositionCampaignModel.direction,
            )
            .having(sa_func.count(PositionCampaignModel.id) > 1)
        )

        if symbol:
            query = query.filter(PositionCampaignModel.symbol == symbol.upper())

        groups = query.all()

        for group_symbol, direction, _count in groups:
            # Get all open campaigns for this group, oldest first
            campaigns = (
                self.session.query(PositionCampaignModel)
                .filter(
                    PositionCampaignModel.account_id == account_id,
                    PositionCampaignModel.symbol == group_symbol,
                    PositionCampaignModel.direction == direction,
                    PositionCampaignModel.status == "open",
                )
                .order_by(PositionCampaignModel.opened_at.asc())
                .all()
            )

            if len(campaigns) < 2:
                continue

            keeper = campaigns[0]
            duplicates = campaigns[1:]

            logger.info(
                "Consolidating %d duplicate %s %s campaigns into campaign %d",
                len(duplicates),
                group_symbol,
                direction,
                keeper.id,
            )

            for dup in duplicates:
                dup_id = dup.id

                # Reassign lots
                lots_moved = (
                    self.session.query(PositionLotModel)
                    .filter(PositionLotModel.campaign_id == dup_id)
                    .update(
                        {PositionLotModel.campaign_id: keeper.id},
                        synchronize_session="fetch",
                    )
                )
                stats["lots_reassigned"] += lots_moved

                # Reassign legs
                legs_moved = (
                    self.session.query(CampaignLegModel)
                    .filter(CampaignLegModel.campaign_id == dup_id)
                    .update(
                        {CampaignLegModel.campaign_id: keeper.id},
                        synchronize_session="fetch",
                    )
                )
                stats["legs_reassigned"] += legs_moved

                # Reassign decision contexts
                self.session.query(DecisionContextModel).filter(
                    DecisionContextModel.campaign_id == dup_id,
                ).update(
                    {DecisionContextModel.campaign_id: keeper.id},
                    synchronize_session="fetch",
                )

                # Reassign trade evaluations
                self.session.query(TradeEvaluationModel).filter(
                    TradeEvaluationModel.campaign_id == dup_id,
                ).update(
                    {TradeEvaluationModel.campaign_id: keeper.id},
                    synchronize_session="fetch",
                )

                # Delete the empty duplicate
                self.session.delete(dup)
                stats["campaigns_removed"] += 1

                logger.info(
                    "Merged campaign %d into %d: %d lots, %d legs moved",
                    dup_id,
                    keeper.id,
                    lots_moved,
                    legs_moved,
                )

            stats["groups_merged"] += 1

        self.session.flush()

        logger.info(
            "Consolidation complete for account %d: %s",
            account_id,
            stats,
        )

        return stats

    def get_orphaned_legs(self, account_id: int) -> list[CampaignLegModel]:
        """Get all orphaned legs (campaign_id IS NULL) for an account.

        Args:
            account_id: Account ID

        Returns:
            List of CampaignLegModel ordered by started_at desc
        """
        return (
            self.session.query(CampaignLegModel)
            .filter(
                CampaignLegModel.campaign_id.is_(None),
                CampaignLegModel.account_id == account_id,
            )
            .order_by(CampaignLegModel.started_at.desc())
            .all()
        )

    def regroup_legs_for_strategy(
        self, account_id: int, symbol: str, strategy_id: int,
    ) -> dict:
        """FIFO-regroup orphaned legs for (symbol, strategy) into campaigns.

        Algorithm:
        1. Collect orphaned legs for (account, symbol) whose DecisionContext
           has strategy_id matching the target.
        2. Sort by started_at ascending.
        3. Track running position: when position==0 start new campaign,
           buy increases, sell decreases. When back to 0, close campaign.
        4. Assign each leg to its computed campaign.

        Args:
            account_id: Account ID
            symbol: Ticker symbol
            strategy_id: Strategy to group by

        Returns:
            Dict with campaigns_created and legs_grouped counts
        """
        # Find orphaned legs for (account, symbol) with matching strategy
        orphaned_legs = (
            self.session.query(CampaignLegModel)
            .join(
                DecisionContextModel,
                DecisionContextModel.leg_id == CampaignLegModel.id,
            )
            .filter(
                CampaignLegModel.campaign_id.is_(None),
                CampaignLegModel.account_id == account_id,
                CampaignLegModel.symbol == symbol,
                DecisionContextModel.strategy_id == strategy_id,
            )
            .order_by(CampaignLegModel.started_at.asc())
            .all()
        )

        if not orphaned_legs:
            logger.debug(
                "No orphaned legs for account=%d symbol=%s strategy=%d",
                account_id, symbol, strategy_id,
            )
            return {"campaigns_created": 0, "legs_grouped": 0}

        campaigns_created = 0
        legs_grouped = 0
        current_campaign = None
        position = 0.0

        for leg in orphaned_legs:
            # Start new campaign if position is flat
            if position == 0.0:
                # Reuse existing open campaign only if all its legs share
                # the same strategy we're regrouping for. This prevents
                # mixing legs from different strategies into one campaign.
                existing_campaign = (
                    self.session.query(PositionCampaignModel)
                    .filter(
                        PositionCampaignModel.account_id == account_id,
                        PositionCampaignModel.symbol == symbol,
                        PositionCampaignModel.direction == leg.direction,
                        PositionCampaignModel.status == "open",
                    )
                    .order_by(PositionCampaignModel.opened_at.asc())
                    .first()
                )

                can_reuse = False
                if existing_campaign:
                    # Check that all existing legs belong to the same strategy
                    other_strategy_count = (
                        self.session.query(CampaignLegModel.id)
                        .join(
                            DecisionContextModel,
                            DecisionContextModel.leg_id == CampaignLegModel.id,
                        )
                        .filter(
                            CampaignLegModel.campaign_id == existing_campaign.id,
                            DecisionContextModel.strategy_id != strategy_id,
                        )
                        .count()
                    )
                    can_reuse = other_strategy_count == 0

                if can_reuse:
                    current_campaign = existing_campaign
                    logger.debug(
                        "Reusing existing campaign %s for %s/%s",
                        current_campaign.id, symbol, strategy_id,
                    )
                else:
                    current_campaign = PositionCampaignModel(
                        account_id=account_id,
                        symbol=symbol,
                        direction=leg.direction,
                        opened_at=leg.started_at,
                        status="open",
                        source="broker_synced",
                    )
                    self.session.add(current_campaign)
                    self.session.flush()  # get the ID
                    campaigns_created += 1
                    logger.debug(
                        "Created campaign %s for %s/%s",
                        current_campaign.id, symbol, strategy_id,
                    )

            # Update running position
            if leg.side == "buy":
                position += leg.quantity
            else:  # sell
                position -= leg.quantity

            # Assign leg to current campaign
            leg.campaign_id = current_campaign.id
            legs_grouped += 1

            # Update DecisionContext campaign_id too
            self.session.query(DecisionContextModel).filter(
                DecisionContextModel.leg_id == leg.id,
            ).update(
                {DecisionContextModel.campaign_id: current_campaign.id},
                synchronize_session="fetch",
            )

            # Position returned to flat: close campaign
            if abs(position) < 1e-9:
                position = 0.0
                current_campaign.status = "closed"
                current_campaign.closed_at = leg.started_at
                # Compute realized P&L from legs
                self._finalize_campaign_from_legs(current_campaign)
                current_campaign = None

        self.session.flush()

        # Clean up campaigns that lost all their legs during regrouping
        empty_campaigns = (
            self.session.query(PositionCampaignModel)
            .outerjoin(
                CampaignLegModel,
                CampaignLegModel.campaign_id == PositionCampaignModel.id,
            )
            .filter(
                PositionCampaignModel.account_id == account_id,
                PositionCampaignModel.symbol == symbol,
                CampaignLegModel.id.is_(None),
            )
            .all()
        )
        campaigns_deleted = 0
        for campaign in empty_campaigns:
            logger.info("Deleting empty campaign %s after regroup", campaign.id)
            self.session.delete(campaign)
            campaigns_deleted += 1

        if campaigns_deleted:
            self.session.flush()

        logger.info(
            "Regrouped %d legs into %d campaigns (deleted %d empty) "
            "for account=%d symbol=%s strategy=%d",
            legs_grouped, campaigns_created, campaigns_deleted,
            account_id, symbol, strategy_id,
        )

        return {"campaigns_created": campaigns_created, "legs_grouped": legs_grouped}

    def _finalize_campaign_from_legs(self, campaign: PositionCampaignModel) -> None:
        """Compute campaign summary fields from its legs.

        Sets qty_opened, qty_closed, avg_open_price, avg_close_price,
        realized_pnl, return_pct, max_qty.
        """
        legs = (
            self.session.query(CampaignLegModel)
            .filter(CampaignLegModel.campaign_id == campaign.id)
            .order_by(CampaignLegModel.started_at.asc())
            .all()
        )

        if not legs:
            return

        total_buy_qty = 0.0
        total_buy_cost = 0.0
        total_sell_qty = 0.0
        total_sell_proceeds = 0.0

        for leg in legs:
            price = leg.avg_price or 0.0
            if leg.side == "buy":
                total_buy_qty += leg.quantity
                total_buy_cost += leg.quantity * price
            else:
                total_sell_qty += leg.quantity
                total_sell_proceeds += leg.quantity * price

        campaign.qty_opened = total_buy_qty
        campaign.qty_closed = total_sell_qty
        campaign.avg_open_price = (
            total_buy_cost / total_buy_qty if total_buy_qty > 0 else None
        )
        campaign.avg_close_price = (
            total_sell_proceeds / total_sell_qty if total_sell_qty > 0 else None
        )
        campaign.max_qty = max(total_buy_qty, total_sell_qty)

        # P&L for long: sell_proceeds - buy_cost
        # P&L for short: buy_cost - sell_proceeds (reversed)
        if campaign.direction == "long":
            campaign.realized_pnl = total_sell_proceeds - total_buy_cost
        else:
            campaign.realized_pnl = total_buy_cost - total_sell_proceeds

        if total_buy_cost > 0:
            campaign.return_pct = (campaign.realized_pnl / total_buy_cost) * 100

    def unwind_legs_after(
        self,
        account_id: int,
        symbol: str,
        strategy_id: int,
        after_timestamp: datetime,
    ) -> list[int]:
        """Unlink legs after a timestamp from campaigns for (symbol, strategy).

        Steps:
        1. Find campaigns containing legs whose DecisionContext.strategy_id matches
        2. Find legs in those campaigns with started_at > after_timestamp
        3. Set campaign_id=NULL on those legs and their DecisionContexts
        4. Delete campaigns that now have zero legs

        Args:
            account_id: Account ID
            symbol: Ticker symbol
            strategy_id: Strategy ID
            after_timestamp: Unlink legs after this time

        Returns:
            List of unlinked leg IDs
        """
        # Find campaigns containing legs whose DecisionContext has the target strategy
        campaign_ids_subq = (
            self.session.query(CampaignLegModel.campaign_id)
            .join(DecisionContextModel, DecisionContextModel.leg_id == CampaignLegModel.id)
            .filter(
                CampaignLegModel.account_id == account_id,
                CampaignLegModel.symbol == symbol,
                CampaignLegModel.campaign_id.isnot(None),
                DecisionContextModel.strategy_id == strategy_id,
            )
            .distinct()
            .subquery()
        )
        campaigns = (
            self.session.query(PositionCampaignModel)
            .filter(PositionCampaignModel.id.in_(campaign_ids_subq))
            .all()
        )

        if not campaigns:
            return []

        campaign_ids = [c.id for c in campaigns]

        # Find legs in those campaigns after the timestamp
        legs_to_unlink = (
            self.session.query(CampaignLegModel)
            .filter(
                CampaignLegModel.campaign_id.in_(campaign_ids),
                CampaignLegModel.started_at > after_timestamp,
            )
            .all()
        )

        if not legs_to_unlink:
            return []

        unlinked_ids = [leg.id for leg in legs_to_unlink]

        # Unlink legs
        for leg in legs_to_unlink:
            leg.campaign_id = None

        # Unlink their DecisionContexts from campaigns
        self.session.query(DecisionContextModel).filter(
            DecisionContextModel.leg_id.in_(unlinked_ids),
        ).update(
            {DecisionContextModel.campaign_id: None},
            synchronize_session="fetch",
        )

        self.session.flush()

        # Clean up empty campaigns
        for campaign in campaigns:
            remaining = (
                self.session.query(CampaignLegModel)
                .filter(CampaignLegModel.campaign_id == campaign.id)
                .count()
            )
            if remaining == 0:
                logger.info("Deleting empty campaign %s after unwind", campaign.id)
                self.session.delete(campaign)

        self.session.flush()

        logger.info(
            "Unwound %d legs after %s for account=%d symbol=%s strategy=%d",
            len(unlinked_ids), after_timestamp, account_id, symbol, strategy_id,
        )

        return unlinked_ids
