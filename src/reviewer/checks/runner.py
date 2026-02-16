"""CheckRunner — orchestrates behavioral checkers for a trade fill.

Fetches ATR and account balance, runs all registered checkers,
and persists CampaignCheck records linked to the DecisionContext.
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
    DecisionContext as DecisionContextModel,
)
from src.data.database.broker_models import TradeFill as TradeFillModel
from src.data.database.trading_buddy_models import (
    UserProfile as UserProfileModel,
)
from src.trade.intent import TradeIntent, TradeDirection, TradeIntentStatus

logger = logging.getLogger(__name__)


class CheckRunner:
    """Runs all registered behavioral checkers against a fill's decision context."""

    def __init__(self, session: Session, settings: ChecksConfig):
        self.session = session
        self.settings = settings
        self.checkers: list[BaseChecker] = [
            RiskSanityChecker(settings),
        ]

    def run_checks(
        self,
        dc: DecisionContextModel,
        fill: TradeFillModel,
    ) -> list[CampaignCheckModel]:
        """Run all checkers for a decision context and persist CampaignCheck records.

        Args:
            dc: The DecisionContext to evaluate
            fill: The linked TradeFill

        Returns:
            List of created CampaignCheck records
        """
        intent = self._build_intent_from_fill(dc, fill)
        atr = self._fetch_atr(fill)
        account_balance = self._get_account_balance(dc.account_id)

        logger.info(
            "Running checks for fill_id=%s dc_id=%s: atr=%s balance=%s",
            fill.id, dc.id, atr, account_balance,
        )

        all_results: list[CheckResult] = []
        for checker in self.checkers:
            try:
                # Pass fill as the "leg" argument — checkers use it for
                # side/quantity/price/symbol data
                results = checker.run(fill, intent, atr, account_balance)
                all_results.extend(results)
            except Exception:
                logger.exception(
                    "Checker %s failed for fill_id=%s",
                    checker.__class__.__name__, fill.id,
                )

        # Persist as CampaignCheck records linked to decision_context
        checks: list[CampaignCheckModel] = []
        for result in all_results:
            check = CampaignCheckModel(
                decision_context_id=dc.id,
                account_id=dc.account_id,
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
            "Persisted %d check records for fill_id=%s dc_id=%s",
            len(checks), fill.id, dc.id,
        )
        return checks

    def _build_intent_from_fill(
        self,
        dc: DecisionContextModel,
        fill: TradeFillModel,
    ) -> Optional[TradeIntent]:
        """Build a TradeIntent domain object from fill data.

        Since intents are no longer persisted, we construct a minimal
        TradeIntent from the fill's trade data for checkers that need it.

        Returns None if the fill doesn't have enough data for an intent.
        """
        try:
            direction = TradeDirection.LONG if fill.side.lower() == "buy" else TradeDirection.SHORT

            return TradeIntent(
                user_id=dc.account_id,
                account_id=dc.account_id,
                symbol=fill.symbol,
                direction=direction,
                timeframe="1Day",  # Default — fills don't carry timeframe
                entry_price=fill.price,
                stop_loss=fill.price,  # No stop data from fill
                profit_target=fill.price,  # No target data from fill
                position_size=fill.quantity,
                position_value=fill.quantity * fill.price,
                status=TradeIntentStatus.EVALUATED,
            )
        except Exception:
            logger.debug(
                "Could not build intent from fill_id=%s", fill.id, exc_info=True,
            )
            return None

    def _fetch_atr(self, fill: TradeFillModel) -> Optional[float]:
        """Fetch the ATR value for this fill's symbol.

        Uses the atr_14 column from the features table.
        Returns None if unavailable.
        """
        try:
            from src.data.database.models import FeatureRow

            row = self.session.query(FeatureRow).filter(
                FeatureRow.symbol == fill.symbol,
            ).order_by(FeatureRow.timestamp.desc()).first()

            if row is None:
                logger.debug("No feature row found for symbol=%s", fill.symbol)
                return None

            atr_value = getattr(row, "atr_14", None)
            if atr_value is not None:
                logger.debug(
                    "Fetched atr_14=%.4f for symbol=%s", atr_value, fill.symbol,
                )
            return atr_value

        except Exception:
            logger.debug(
                "Could not fetch ATR for fill_id=%s: feature table may not exist",
                fill.id, exc_info=True,
            )
            return None

    def _get_account_balance(self, account_id: int) -> Optional[float]:
        """Get the account balance for a user."""
        try:
            profile = self.session.query(UserProfileModel).filter(
                UserProfileModel.user_account_id == account_id,
            ).first()

            if profile is None:
                logger.debug("No profile found for account_id=%s", account_id)
                return None

            balance = profile.account_balance
            logger.debug(
                "Account balance=%.2f for account_id=%s",
                balance or 0, account_id,
            )
            return balance

        except Exception:
            logger.debug(
                "Could not fetch account balance for account_id=%s",
                account_id, exc_info=True,
            )
            return None
