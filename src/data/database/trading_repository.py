"""Repository for Trading Buddy data access.

Provides methods for:
- Loading user accounts and rules
- Persisting trade intents and evaluations
- Converting database models to domain objects
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
