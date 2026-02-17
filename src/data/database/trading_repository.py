"""Repository for Trading Buddy data access.

Provides methods for:
- Loading user accounts and rules
- Managing strategies
- Trade fill operations
- Decision context operations (1-to-1 with fills)
- Campaign rebuild service (derived campaigns from fills)
- Campaign check operations
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src.data.database.trading_buddy_models import (
    UserAccount as UserAccountModel,
    UserProfile as UserProfileModel,
    UserRule as UserRuleModel,
    Waitlist as WaitlistModel,
)
from src.data.database.broker_models import TradeFill as TradeFillModel
from src.data.database.strategy_models import Strategy as StrategyModel
from src.data.database.trade_lifecycle_models import (
    CampaignCheck as CampaignCheckModel,
    DecisionContext as DecisionContextModel,
    CampaignFill as CampaignFillModel,
)
from src.trade.evaluation import Severity
from src.evaluators.base import EvaluatorConfig

logger = logging.getLogger(__name__)


class TradingBuddyRepository:
    """Repository for Trading Buddy data operations.

    Provides methods for loading user configuration,
    managing fills, decision contexts, and campaigns.
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
        """Get user account by external user ID."""
        return self.session.query(UserAccountModel).filter(
            UserAccountModel.external_user_id == external_id
        ).first()

    def get_account(self, account_id: int) -> Optional[UserAccountModel]:
        """Get user account by ID."""
        return self.session.query(UserAccountModel).filter(
            UserAccountModel.id == account_id
        ).first()

    def get_account_by_email(self, email: str) -> Optional[UserAccountModel]:
        """Get user account by email."""
        return self.session.query(UserAccountModel).filter(
            UserAccountModel.email == email
        ).first()

    def get_account_by_google_id(self, google_id: str) -> Optional[UserAccountModel]:
        """Get user account by Google ID."""
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
        """Create a new user account."""
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

    # -------------------------------------------------------------------------
    # Waitlist Operations
    # -------------------------------------------------------------------------

    def get_waitlist_entry_by_email(self, email: str) -> Optional[WaitlistModel]:
        """Get a waitlist entry by email."""
        return self.session.query(WaitlistModel).filter(
            WaitlistModel.email == email
        ).first()

    def is_email_approved(self, email: str) -> bool:
        """Check if an email is approved on the waitlist."""
        entry = self.get_waitlist_entry_by_email(email)
        return entry is not None and entry.status == "approved"

    def create_waitlist_entry(
        self,
        name: str,
        email: str,
        referral_source: Optional[str] = None,
    ) -> WaitlistModel:
        """Create a new waitlist entry."""
        entry = WaitlistModel(
            name=name,
            email=email,
            referral_source=referral_source,
        )
        self.session.add(entry)
        self.session.flush()
        logger.info("Created waitlist entry id=%s email=%s", entry.id, email)
        return entry

    def get_or_create_waitlist_entry(
        self,
        name: str,
        email: str,
        referral_source: Optional[str] = None,
    ) -> tuple[WaitlistModel, bool]:
        """Get existing waitlist entry or create a new one.

        Returns:
            Tuple of (entry, created) where created is True if new.
        """
        existing = self.get_waitlist_entry_by_email(email)
        if existing is not None:
            return existing, False
        entry = self.create_waitlist_entry(name, email, referral_source)
        return entry, True

    # -------------------------------------------------------------------------
    # User Profile Operations
    # -------------------------------------------------------------------------

    def get_profile(self, account_id: int) -> Optional[UserProfileModel]:
        """Get user profile by account ID."""
        return self.session.query(UserProfileModel).filter(
            UserProfileModel.user_account_id == account_id
        ).first()

    def create_profile(self, account_id: int, **kwargs) -> UserProfileModel:
        """Create a user profile with default risk params.

        Accepts either flat kwargs or structured dicts (profile={...}, risk_profile={...}).
        """
        profile_data = dict(UserProfileModel.PROFILE_DEFAULTS)
        risk_data = dict(UserProfileModel.RISK_PROFILE_DEFAULTS)
        site_prefs_data = None

        if "profile" in kwargs:
            profile_data.update(kwargs.pop("profile"))
        if "risk_profile" in kwargs:
            risk_data.update(kwargs.pop("risk_profile"))
        if "site_prefs" in kwargs:
            site_prefs_data = dict(UserProfileModel.SITE_PREF_DEFAULTS)
            site_prefs_data.update(kwargs.pop("site_prefs"))

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
        """Get existing profile or create one with defaults."""
        profile = self.get_profile(account_id)
        if profile is None:
            profile = self.create_profile(account_id)
        return profile

    def update_profile(self, account_id: int, **kwargs) -> Optional[UserProfileModel]:
        """Update user profile fields.

        Accepts either flat kwargs or structured dicts.
        """
        existing = self.get_profile(account_id)
        if existing is None:
            return None

        profile_keys = set(UserProfileModel.PROFILE_DEFAULTS.keys())
        risk_keys = set(UserProfileModel.RISK_PROFILE_DEFAULTS.keys())
        site_pref_keys = set(UserProfileModel.SITE_PREF_DEFAULTS.keys())

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
        """Get user rules for an account."""
        query = self.session.query(UserRuleModel).filter(
            UserRuleModel.account_id == account_id
        )
        if evaluator:
            query = query.filter(UserRuleModel.evaluator == evaluator)
        if enabled_only:
            query = query.filter(UserRuleModel.is_enabled == True)  # noqa: E712
        return query.all()

    def build_evaluator_configs(
        self,
        account_id: int,
        strategy_id: Optional[int] = None,
    ) -> dict[str, EvaluatorConfig]:
        """Build EvaluatorConfig objects from user profile, rules, and strategy."""
        account = self.get_account(account_id)
        if not account:
            return {}

        profile = self.get_or_create_profile(account_id)
        rules = self.get_user_rules(account_id)

        base_params = {
            "account_balance": profile.account_balance,
            "max_position_size_pct": profile.max_position_size_pct,
            "max_risk_per_trade_pct": profile.max_risk_per_trade_pct,
            "min_rr_ratio": profile.min_risk_reward_ratio,
        }

        if strategy_id is not None:
            strategy = self.get_strategy(strategy_id)
            if strategy and strategy.risk_profile:
                logger.info(
                    "Applying strategy risk overrides: strategy_id=%s overrides=%s",
                    strategy_id, strategy.risk_profile,
                )
                key_mapping = {
                    "max_position_size_pct": "max_position_size_pct",
                    "max_risk_per_trade_pct": "max_risk_per_trade_pct",
                    "max_daily_loss_pct": "max_daily_loss_pct",
                    "min_risk_reward_ratio": "min_rr_ratio",
                }
                for risk_key, param_key in key_mapping.items():
                    if risk_key in strategy.risk_profile:
                        base_params[param_key] = strategy.risk_profile[risk_key]

        rules_by_evaluator: dict[str, list[UserRuleModel]] = {}
        for rule in rules:
            if rule.evaluator not in rules_by_evaluator:
                rules_by_evaluator[rule.evaluator] = []
            rules_by_evaluator[rule.evaluator].append(rule)

        configs: dict[str, EvaluatorConfig] = {}
        for evaluator_name, evaluator_rules in rules_by_evaluator.items():
            thresholds = {}
            severity_overrides = {}
            custom_params = base_params.copy()

            for rule in evaluator_rules:
                params = rule.parameters or {}
                if "threshold" in params:
                    thresholds[rule.rule_code] = params["threshold"]
                if "thresholds" in params:
                    thresholds.update(params["thresholds"])
                if "severity" in params:
                    severity_overrides[rule.rule_code] = Severity(params["severity"])
                for key, value in params.items():
                    if key not in ("threshold", "thresholds", "severity"):
                        custom_params[key] = value

            configs[evaluator_name] = EvaluatorConfig(
                enabled=True,
                thresholds=thresholds,
                severity_overrides=severity_overrides,
                custom_params=custom_params,
            )

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
        """Create a new strategy for an account."""
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
        """Get a strategy by ID."""
        return self.session.query(StrategyModel).filter(
            StrategyModel.id == strategy_id
        ).first()

    def get_strategy_by_name(
        self,
        account_id: int,
        name: str,
    ) -> Optional[StrategyModel]:
        """Get a strategy by account and name."""
        return self.session.query(StrategyModel).filter(
            StrategyModel.account_id == account_id,
            StrategyModel.name == name,
        ).first()

    def get_strategies_for_account(
        self,
        account_id: int,
        active_only: bool = True,
    ) -> list[StrategyModel]:
        """Get all strategies for an account."""
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
        """Update strategy fields."""
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

    # -------------------------------------------------------------------------
    # Trade Fill Operations
    # -------------------------------------------------------------------------

    def create_trade_fill(self, **kwargs) -> TradeFillModel:
        """Create a trade fill record."""
        fill = TradeFillModel(**kwargs)
        self.session.add(fill)
        self.session.flush()
        logger.info("Created trade fill id=%s symbol=%s side=%s", fill.id, fill.symbol, fill.side)
        return fill

    # -------------------------------------------------------------------------
    # Decision Context Operations (1-to-1 with fills)
    # -------------------------------------------------------------------------

    def create_decision_context(self, **kwargs) -> DecisionContextModel:
        """Create a decision context record linked to a fill."""
        context = DecisionContextModel(**kwargs)
        self.session.add(context)
        self.session.flush()
        logger.info(
            "Created decision context id=%s type=%s fill_id=%s",
            context.id, context.context_type, context.fill_id,
        )
        return context

    def get_or_create_decision_context(
        self,
        fill_id: int,
        account_id: int,
        context_type: str = "entry",
        **kwargs,
    ) -> DecisionContextModel:
        """Get existing decision context for a fill, or create one.

        Args:
            fill_id: Trade fill ID (unique per context)
            account_id: Account ID
            context_type: Context type (entry, exit, etc.)
            **kwargs: Additional context fields

        Returns:
            Existing or newly created DecisionContextModel
        """
        existing = self.session.query(DecisionContextModel).filter(
            DecisionContextModel.fill_id == fill_id
        ).first()

        if existing:
            return existing

        return self.create_decision_context(
            fill_id=fill_id,
            account_id=account_id,
            context_type=context_type,
            **kwargs,
        )

    def get_context(self, context_id: int) -> Optional[DecisionContextModel]:
        """Get a decision context by ID."""
        return self.session.query(DecisionContextModel).filter(
            DecisionContextModel.id == context_id
        ).first()

    # -------------------------------------------------------------------------
    # Campaign Rebuild Service
    # -------------------------------------------------------------------------

    def rebuild_campaigns(
        self,
        account_id: int,
        symbol: str,
        strategy_id: Optional[int],
    ) -> dict:
        """Rebuild campaigns for a (symbol, strategy) group from fills.

        Algorithm:
        1. Query fills joined with decision_contexts filtered by account, symbol, strategy
        2. Walk chronologically tracking net position
        3. Campaign boundaries at zero crossings
        4. group_id = first fill_id in each campaign group

        Args:
            account_id: Account ID
            symbol: Symbol to rebuild campaigns for
            strategy_id: Strategy ID (None for untagged fills)

        Returns:
            Dict with stats: campaigns_created, fills_grouped
        """
        stats = {"campaigns_created": 0, "fills_grouped": 0}

        # Delete existing campaign_fills for this group by joining to matching fills
        fill_ids_subquery = (
            self.session.query(TradeFillModel.id)
            .outerjoin(
                DecisionContextModel,
                DecisionContextModel.fill_id == TradeFillModel.id,
            )
            .filter(
                TradeFillModel.account_id == account_id,
                TradeFillModel.symbol == symbol,
            )
        )
        if strategy_id is not None:
            fill_ids_subquery = fill_ids_subquery.filter(
                DecisionContextModel.strategy_id == strategy_id
            )
        else:
            fill_ids_subquery = fill_ids_subquery.filter(
                (DecisionContextModel.strategy_id.is_(None))
                | (DecisionContextModel.id.is_(None))
            )

        fill_ids = [row[0] for row in fill_ids_subquery.all()]

        if fill_ids:
            self.session.query(CampaignFillModel).filter(
                CampaignFillModel.fill_id.in_(fill_ids)
            ).delete(synchronize_session="fetch")
            self.session.flush()

        # Query fills with their decision context strategy
        query = (
            self.session.query(TradeFillModel)
            .outerjoin(
                DecisionContextModel,
                DecisionContextModel.fill_id == TradeFillModel.id,
            )
            .filter(
                TradeFillModel.account_id == account_id,
                TradeFillModel.symbol == symbol,
            )
        )

        if strategy_id is not None:
            query = query.filter(DecisionContextModel.strategy_id == strategy_id)
        else:
            query = query.filter(
                (DecisionContextModel.strategy_id.is_(None))
                | (DecisionContextModel.id.is_(None))
            )

        fills = query.order_by(TradeFillModel.executed_at.asc()).all()

        if not fills:
            logger.debug(
                "No fills for rebuild: account=%s symbol=%s strategy=%s",
                account_id, symbol, strategy_id,
            )
            return stats

        # Walk fills chronologically, tracking net position
        position = 0.0
        current_fills: list[TradeFillModel] = []

        for fill in fills:
            delta = fill.quantity if fill.side.lower() == "buy" else -fill.quantity
            prev_position = position
            position += delta

            current_fills.append(fill)

            # Check for zero crossing
            if position == 0.0:
                # Campaign complete — create it
                self._create_campaign_from_fills(current_fills)
                stats["campaigns_created"] += 1
                stats["fills_grouped"] += len(current_fills)
                current_fills = []
            elif prev_position != 0.0 and (
                (prev_position > 0 and position < 0)
                or (prev_position < 0 and position > 0)
            ):
                # Zero crossing flip: the fill both closes old and opens new.
                # Close old campaign with all fills up to and including this one
                self._create_campaign_from_fills(current_fills)
                stats["campaigns_created"] += 1
                stats["fills_grouped"] += len(current_fills)
                # Start new campaign with this fill (it opens the new direction)
                current_fills = [fill]

        # Remaining fills form an open campaign
        if current_fills:
            self._create_campaign_from_fills(current_fills)
            stats["campaigns_created"] += 1
            stats["fills_grouped"] += len(current_fills)

        logger.info(
            "Rebuilt campaigns: account=%s symbol=%s strategy=%s stats=%s",
            account_id, symbol, strategy_id, stats,
        )
        return stats

    def _create_campaign_from_fills(
        self,
        fills: list[TradeFillModel],
    ) -> int:
        """Create campaign_fill rows for a group of fills.

        group_id is set to the first fill's ID (deterministic, unique per campaign).

        Args:
            fills: List of fills in this campaign

        Returns:
            The group_id for the created campaign
        """
        group_id = fills[0].id

        for fill in fills:
            cf = CampaignFillModel(
                group_id=group_id,
                fill_id=fill.id,
            )
            self.session.add(cf)

        self.session.flush()
        logger.debug(
            "Created campaign group_id=%s fills=%d",
            group_id, len(fills),
        )
        return group_id

    def rebuild_all_campaigns(self, account_id: int) -> dict:
        """Rebuild all campaigns for a user (used after bulk sync).

        Groups fills by (symbol, strategy_id) and rebuilds each group.

        Args:
            account_id: Account ID

        Returns:
            Dict with aggregate stats
        """
        total_stats = {"campaigns_created": 0, "fills_grouped": 0, "groups_rebuilt": 0}

        # First ensure all fills have a decision context
        self._ensure_decision_contexts(account_id)

        # Find all unique (symbol, strategy_id) groups
        from sqlalchemy import distinct

        # Get all symbols for this account
        symbols = (
            self.session.query(distinct(TradeFillModel.symbol))
            .filter(TradeFillModel.account_id == account_id)
            .all()
        )

        for (symbol,) in symbols:
            # Get all strategy IDs for this symbol (including None)
            strategy_ids = (
                self.session.query(distinct(DecisionContextModel.strategy_id))
                .join(TradeFillModel, TradeFillModel.id == DecisionContextModel.fill_id)
                .filter(
                    TradeFillModel.account_id == account_id,
                    TradeFillModel.symbol == symbol,
                )
                .all()
            )

            # Also include fills without a decision context (strategy=None)
            has_unlinked = (
                self.session.query(TradeFillModel.id)
                .outerjoin(
                    DecisionContextModel,
                    DecisionContextModel.fill_id == TradeFillModel.id,
                )
                .filter(
                    TradeFillModel.account_id == account_id,
                    TradeFillModel.symbol == symbol,
                    DecisionContextModel.id.is_(None),
                )
                .first()
            )

            strategy_id_set: set[Optional[int]] = set()
            for (sid,) in strategy_ids:
                strategy_id_set.add(sid)
            if has_unlinked:
                strategy_id_set.add(None)

            for strategy_id in strategy_id_set:
                group_stats = self.rebuild_campaigns(account_id, symbol, strategy_id)
                total_stats["campaigns_created"] += group_stats["campaigns_created"]
                total_stats["fills_grouped"] += group_stats["fills_grouped"]
                total_stats["groups_rebuilt"] += 1

        logger.info(
            "Rebuilt all campaigns for account=%s: %s", account_id, total_stats,
        )
        return total_stats

    def _ensure_decision_contexts(self, account_id: int) -> int:
        """Create decision contexts for fills that don't have one.

        Returns count of contexts created.
        """
        fills_without_dc = (
            self.session.query(TradeFillModel)
            .outerjoin(
                DecisionContextModel,
                DecisionContextModel.fill_id == TradeFillModel.id,
            )
            .filter(
                TradeFillModel.account_id == account_id,
                DecisionContextModel.id.is_(None),
            )
            .all()
        )

        created = 0
        for fill in fills_without_dc:
            context_type = "entry" if fill.side.lower() == "buy" else "exit"
            self.create_decision_context(
                fill_id=fill.id,
                account_id=account_id,
                context_type=context_type,
            )
            created += 1

        if created:
            self.session.flush()
            logger.info(
                "Created %d decision contexts for account=%s",
                created, account_id,
            )
        return created

    def on_strategy_updated(
        self,
        account_id: int,
        fill_id: int,
        old_strategy_id: Optional[int],
        new_strategy_id: Optional[int],
    ) -> None:
        """Handle strategy change on a fill — delete and rebuild affected groups.

        When a fill's strategy changes from A to B:
        1. Delete and rebuild campaigns for (symbol, A)
        2. Delete and rebuild campaigns for (symbol, B)

        Args:
            account_id: Account ID
            fill_id: The fill whose strategy changed
            old_strategy_id: Previous strategy (or None)
            new_strategy_id: New strategy (or None)
        """
        fill = self.session.query(TradeFillModel).filter(
            TradeFillModel.id == fill_id,
            TradeFillModel.account_id == account_id,
        ).first()

        if not fill:
            logger.warning("Fill id=%s not found for strategy update", fill_id)
            return

        symbol = fill.symbol

        # Rebuild old group if it had a strategy
        if old_strategy_id is not None or old_strategy_id != new_strategy_id:
            self.rebuild_campaigns(account_id, symbol, old_strategy_id)

        # Rebuild new group
        if new_strategy_id != old_strategy_id:
            self.rebuild_campaigns(account_id, symbol, new_strategy_id)

        logger.info(
            "Strategy updated on fill=%s: %s -> %s, rebuilt campaigns for %s",
            fill_id, old_strategy_id, new_strategy_id, symbol,
        )

    # -------------------------------------------------------------------------
    # Campaign Query Operations
    # -------------------------------------------------------------------------

    def get_campaigns(
        self,
        account_id: int,
        symbol: Optional[str] = None,
        strategy_id: Optional[int] = None,
        limit: int = 200,
    ) -> list[dict]:
        """Get campaigns for an account, optionally filtered.

        Returns list of dicts with: group_id, symbol, account_id, strategy_id,
        first_fill_at (for ordering).
        """
        from sqlalchemy import distinct, func

        # Get distinct group_ids with their first fill info
        query = (
            self.session.query(
                CampaignFillModel.group_id,
                func.min(TradeFillModel.executed_at).label("first_fill_at"),
            )
            .join(TradeFillModel, TradeFillModel.id == CampaignFillModel.fill_id)
            .filter(TradeFillModel.account_id == account_id)
        )

        if symbol:
            query = query.filter(TradeFillModel.symbol == symbol)

        if strategy_id is not None:
            query = query.outerjoin(
                DecisionContextModel,
                DecisionContextModel.fill_id == TradeFillModel.id,
            ).filter(DecisionContextModel.strategy_id == strategy_id)

        query = query.group_by(CampaignFillModel.group_id)
        query = query.order_by(func.min(TradeFillModel.executed_at).desc())
        query = query.limit(limit)

        rows = query.all()

        campaigns = []
        for row in rows:
            campaigns.append({
                "group_id": row.group_id,
                "first_fill_at": row.first_fill_at,
            })

        return campaigns

    def get_campaign_fills(self, group_id: int) -> list[TradeFillModel]:
        """Get fills for a campaign group, ordered by executed_at."""
        return (
            self.session.query(TradeFillModel)
            .join(CampaignFillModel, CampaignFillModel.fill_id == TradeFillModel.id)
            .filter(CampaignFillModel.group_id == group_id)
            .order_by(TradeFillModel.executed_at.asc())
            .all()
        )

    def campaign_group_exists(self, group_id: int, account_id: int) -> bool:
        """Check if a campaign group exists and belongs to the account."""
        return (
            self.session.query(CampaignFillModel.id)
            .join(TradeFillModel, TradeFillModel.id == CampaignFillModel.fill_id)
            .filter(
                CampaignFillModel.group_id == group_id,
                TradeFillModel.account_id == account_id,
            )
            .first()
        ) is not None

    def count_campaign_groups(
        self,
        account_id: int,
        symbol: Optional[str] = None,
    ) -> int:
        """Count distinct campaign groups for an account, optionally by symbol."""
        from sqlalchemy import func

        query = (
            self.session.query(func.count(func.distinct(CampaignFillModel.group_id)))
            .join(TradeFillModel, TradeFillModel.id == CampaignFillModel.fill_id)
            .filter(TradeFillModel.account_id == account_id)
        )
        if symbol:
            query = query.filter(TradeFillModel.symbol == symbol)
        return query.scalar() or 0

    def count_closed_campaign_groups(
        self,
        account_id: int,
        symbol: Optional[str] = None,
    ) -> int:
        """Count campaign groups that are closed (net position = 0).

        A closed campaign has equal buy and sell quantities across its fills.
        """
        from sqlalchemy import func

        # Get all group_ids for this account/symbol
        query = (
            self.session.query(CampaignFillModel.group_id)
            .join(TradeFillModel, TradeFillModel.id == CampaignFillModel.fill_id)
            .filter(TradeFillModel.account_id == account_id)
        )
        if symbol:
            query = query.filter(TradeFillModel.symbol == symbol)

        group_ids = [row[0] for row in query.distinct().all()]

        closed_count = 0
        for gid in group_ids:
            fills = self.get_campaign_fills(gid)
            net_qty = 0.0
            for fill in fills:
                if fill.side.lower() == "buy":
                    net_qty += fill.quantity
                else:
                    net_qty -= fill.quantity
            if abs(net_qty) < 1e-9:
                closed_count += 1

        return closed_count

    def count_grouped_fills(self, account_id: int) -> int:
        """Count fills that are assigned to at least one campaign group."""
        from sqlalchemy import func

        return (
            self.session.query(func.count(func.distinct(CampaignFillModel.fill_id)))
            .join(TradeFillModel, TradeFillModel.id == CampaignFillModel.fill_id)
            .filter(TradeFillModel.account_id == account_id)
            .scalar()
        ) or 0

    # -------------------------------------------------------------------------
    # Batch-load methods (N+1 elimination)
    # -------------------------------------------------------------------------

    def get_decision_contexts_for_fills(
        self, fill_ids: list[int],
    ) -> dict[int, DecisionContextModel]:
        """Batch-load decision contexts keyed by fill_id.

        Args:
            fill_ids: List of TradeFill IDs

        Returns:
            Dict mapping fill_id -> DecisionContext
        """
        if not fill_ids:
            return {}

        rows = (
            self.session.query(DecisionContextModel)
            .filter(DecisionContextModel.fill_id.in_(fill_ids))
            .all()
        )
        return {dc.fill_id: dc for dc in rows}

    def get_strategies_by_ids(
        self, strategy_ids: list[int],
    ) -> dict[int, StrategyModel]:
        """Batch-load strategies keyed by strategy ID.

        Args:
            strategy_ids: List of Strategy IDs

        Returns:
            Dict mapping strategy_id -> Strategy
        """
        if not strategy_ids:
            return {}

        rows = (
            self.session.query(StrategyModel)
            .filter(StrategyModel.id.in_(strategy_ids))
            .all()
        )
        return {s.id: s for s in rows}

    def get_checks_for_contexts(
        self, context_ids: list[int],
    ) -> dict[int, list[CampaignCheckModel]]:
        """Batch-load campaign checks keyed by decision_context_id.

        Args:
            context_ids: List of DecisionContext IDs

        Returns:
            Dict mapping decision_context_id -> list of CampaignCheck
        """
        if not context_ids:
            return {}

        rows = (
            self.session.query(CampaignCheckModel)
            .filter(CampaignCheckModel.decision_context_id.in_(context_ids))
            .order_by(CampaignCheckModel.checked_at.asc())
            .all()
        )

        result: dict[int, list[CampaignCheckModel]] = {}
        for check in rows:
            result.setdefault(check.decision_context_id, []).append(check)
        return result
