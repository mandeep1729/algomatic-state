"""CheckRunner — orchestrates behavioral checkers for a campaign leg.

Loads the linked TradeIntent (if any), fetches ATR and account balance,
runs all registered checkers, and persists CampaignCheck records.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from config.settings import ChecksConfig
from src.reviewer.checks.base import BaseChecker, CheckResult
from src.reviewer.checks.risk_sanity import RiskSanityChecker
from src.data.database.trade_lifecycle_models import (
    CampaignCheck as CampaignCheckModel,
    CampaignLeg as CampaignLegModel,
)
from src.data.database.trading_buddy_models import (
    UserProfile as UserProfileModel,
)
from src.trade.intent import TradeIntent, TradeDirection, TradeIntentStatus

logger = logging.getLogger(__name__)


class CheckRunner:
    """Runs all registered behavioral checkers against a campaign leg."""

    def __init__(self, session: Session, settings: ChecksConfig):
        self.session = session
        self.settings = settings
        self.checkers: list[BaseChecker] = [
            RiskSanityChecker(settings),
        ]

    def run_checks(self, leg: CampaignLegModel) -> list[CampaignCheckModel]:
        """Run all checkers for a leg and persist CampaignCheck records.

        Args:
            leg: The CampaignLeg to evaluate

        Returns:
            List of created CampaignCheck records
        """
        intent = self._load_intent(leg)
        atr = self._fetch_atr(leg)
        account_balance = self._get_account_balance(leg)

        logger.info(
            "Running checks for leg_id=%s campaign_id=%s: "
            "intent=%s atr=%s balance=%s",
            leg.id, leg.campaign_id,
            intent.intent_id if intent else None,
            atr, account_balance,
        )

        all_results: list[CheckResult] = []
        for checker in self.checkers:
            try:
                results = checker.run(leg, intent, atr, account_balance)
                all_results.extend(results)
            except Exception:
                logger.exception(
                    "Checker %s failed for leg_id=%s",
                    checker.__class__.__name__, leg.id,
                )

        # Persist as CampaignCheck records
        checks: list[CampaignCheckModel] = []
        for result in all_results:
            check = CampaignCheckModel(
                leg_id=leg.id,
                account_id=leg.campaign.account_id,
                check_type=result.check_type,
                severity=result.severity,
                passed=result.passed,
                details=result.details,
                nudge_text=result.nudge_text,
                check_phase=result.check_phase,
                checked_at=datetime.utcnow(),
            )
            self.session.add(check)
            checks.append(check)

        self.session.flush()
        logger.info(
            "Persisted %d check records for leg_id=%s",
            len(checks), leg.id,
        )
        return checks

    def _load_intent(self, leg: CampaignLegModel) -> Optional[TradeIntent]:
        """Load the TradeIntent linked to this leg, if any.

        Args:
            leg: CampaignLeg model

        Returns:
            Domain TradeIntent or None
        """
        if leg.intent_id is None:
            logger.debug("No intent_id on leg_id=%s", leg.id)
            return None

        from src.data.database.trading_buddy_models import (
            TradeIntent as TradeIntentModel,
        )

        model = self.session.query(TradeIntentModel).filter(
            TradeIntentModel.id == leg.intent_id
        ).first()

        if model is None:
            logger.warning(
                "Intent id=%s not found for leg_id=%s", leg.intent_id, leg.id,
            )
            return None

        return TradeIntent(
            intent_id=model.id,
            user_id=model.account_id,
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

    def _fetch_atr(self, leg: CampaignLegModel) -> Optional[float]:
        """Fetch the ATR value for this leg's symbol/timeframe.

        Uses the same atr_14 column from the features table that
        ContextPackBuilder reads. Returns None if unavailable.

        Args:
            leg: CampaignLeg model

        Returns:
            ATR float value or None
        """
        try:
            campaign = leg.campaign
            if campaign is None:
                logger.debug("No campaign found for leg %s, skipping ATR fetch", leg.id)
                return None

            from src.data.database.models import FeatureRow

            row = self.session.query(FeatureRow).filter(
                FeatureRow.symbol == campaign.symbol,
            ).order_by(FeatureRow.timestamp.desc()).first()

            if row is None:
                logger.debug(
                    "No feature row found for symbol=%s", campaign.symbol,
                )
                return None

            atr_value = getattr(row, "atr_14", None)
            if atr_value is not None:
                logger.debug(
                    "Fetched atr_14=%.4f for symbol=%s", atr_value, campaign.symbol,
                )
            return atr_value

        except Exception:
            logger.debug(
                "Could not fetch ATR for leg_id=%s: feature table may not exist",
                leg.id,
                exc_info=True,
            )
            return None

    def _get_account_balance(self, leg: CampaignLegModel) -> Optional[float]:
        """Get the account balance for the campaign's account.

        Args:
            leg: CampaignLeg model

        Returns:
            Account balance or None
        """
        try:
            campaign = leg.campaign
            if campaign is None:
                logger.debug("No campaign found for leg %s, skipping balance lookup", leg.id)
                return None

            profile = self.session.query(UserProfileModel).filter(
                UserProfileModel.user_account_id == campaign.account_id,
            ).first()

            if profile is None:
                logger.debug(
                    "No profile found for account_id=%s", campaign.account_id,
                )
                return None

            balance = profile.account_balance
            logger.debug(
                "Account balance=%.2f for account_id=%s",
                balance or 0, campaign.account_id,
            )
            return balance

        except Exception:
            logger.debug(
                "Could not fetch account balance for leg_id=%s",
                leg.id,
                exc_info=True,
            )
            return None
