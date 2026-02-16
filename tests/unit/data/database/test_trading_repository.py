"""Unit tests for TradingBuddyRepository campaign rebuild and strategy risk profiles.

Tests the zero-crossing campaign rebuild algorithm, decision context
operations, and strategy-level risk_profile overrides in evaluator config
building.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.data.database.trading_repository import TradingBuddyRepository
from src.data.database.broker_models import TradeFill as TradeFillModel
from src.data.database.strategy_models import Strategy as StrategyModel
from src.data.database.trading_buddy_models import (
    UserProfile as UserProfileModel,
)
from src.data.database.trade_lifecycle_models import (
    Campaign as CampaignModel,
    CampaignFill as CampaignFillModel,
    DecisionContext as DecisionContextModel,
)


@pytest.fixture
def mock_session():
    """Create a mock SQLAlchemy session."""
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = []
    session.query.return_value.filter.return_value.first.return_value = None
    return session


@pytest.fixture
def repository(mock_session):
    """Create repository with mock session."""
    return TradingBuddyRepository(mock_session)


def make_fill(
    id: int,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    executed_at: datetime,
    account_id: int = 1,
) -> TradeFillModel:
    """Create a mock TradeFillModel."""
    fill = MagicMock(spec=TradeFillModel)
    fill.id = id
    fill.symbol = symbol
    fill.side = side
    fill.quantity = quantity
    fill.price = price
    fill.executed_at = executed_at
    fill.account_id = account_id
    return fill


class TestRebuildCampaigns:
    """Tests for rebuild_campaigns zero-crossing algorithm."""

    def test_returns_zero_stats_when_no_fills(self, repository, mock_session):
        """Test that empty stats are returned when no fills exist."""
        # Mock: no existing campaigns to delete
        mock_session.query.return_value.filter.return_value.all.return_value = []
        # Mock: outerjoin().filter() for fills query returns empty
        mock_session.query.return_value.outerjoin.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = repository.rebuild_campaigns(account_id=1, symbol="AAPL", strategy_id=None)

        assert result["campaigns_created"] == 0
        assert result["fills_grouped"] == 0

    def test_simple_round_trip_creates_one_campaign(self, repository, mock_session):
        """Test buy->sell round trip creates exactly one campaign."""
        now = datetime.now(timezone.utc)
        buy = make_fill(1, "AAPL", "buy", 10, 150.0, now)
        sell = make_fill(2, "AAPL", "sell", 10, 160.0, now + timedelta(hours=1))

        # Mock: no existing campaigns
        mock_session.query.return_value.filter.return_value.all.return_value = []
        # Mock: fills query returns buy + sell
        mock_session.query.return_value.outerjoin.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
            buy, sell,
        ]

        # Track session.add calls
        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        result = repository.rebuild_campaigns(account_id=1, symbol="AAPL", strategy_id=None)

        assert result["campaigns_created"] == 1
        assert result["fills_grouped"] == 2

        # Verify we created a Campaign and 2 CampaignFills
        campaigns = [o for o in added_objects if isinstance(o, CampaignModel)]
        campaign_fills = [o for o in added_objects if isinstance(o, CampaignFillModel)]
        assert len(campaigns) == 1
        assert campaigns[0].symbol == "AAPL"
        assert campaigns[0].account_id == 1
        assert len(campaign_fills) == 2

    def test_open_position_creates_open_campaign(self, repository, mock_session):
        """Test a buy without matching sell creates an open campaign."""
        now = datetime.now(timezone.utc)
        buy = make_fill(1, "AAPL", "buy", 10, 150.0, now)

        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_session.query.return_value.outerjoin.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [buy]

        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        result = repository.rebuild_campaigns(account_id=1, symbol="AAPL", strategy_id=None)

        assert result["campaigns_created"] == 1
        assert result["fills_grouped"] == 1

    def test_two_round_trips_create_two_campaigns(self, repository, mock_session):
        """Test two complete round trips create two campaigns."""
        now = datetime.now(timezone.utc)
        fills = [
            make_fill(1, "AAPL", "buy", 10, 150.0, now),
            make_fill(2, "AAPL", "sell", 10, 160.0, now + timedelta(hours=1)),
            make_fill(3, "AAPL", "buy", 5, 155.0, now + timedelta(hours=2)),
            make_fill(4, "AAPL", "sell", 5, 170.0, now + timedelta(hours=3)),
        ]

        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_session.query.return_value.outerjoin.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = fills

        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        result = repository.rebuild_campaigns(account_id=1, symbol="AAPL", strategy_id=None)

        assert result["campaigns_created"] == 2
        assert result["fills_grouped"] == 4

    def test_zero_crossing_flip_creates_two_campaigns(self, repository, mock_session):
        """Test a flip from long to short creates two campaigns.

        Example: Buy 10, Sell 15 → net -5 (crosses zero)
        First campaign: buy 10 + sell 15 (closed by crossing)
        Second campaign: sell 15 (opens new short, still open)
        """
        now = datetime.now(timezone.utc)
        buy = make_fill(1, "AAPL", "buy", 10, 150.0, now)
        sell = make_fill(2, "AAPL", "sell", 15, 160.0, now + timedelta(hours=1))

        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_session.query.return_value.outerjoin.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
            buy, sell,
        ]

        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        result = repository.rebuild_campaigns(account_id=1, symbol="AAPL", strategy_id=None)

        # First campaign: buy 10 + sell 15 (zero crossing close)
        # Second campaign: sell 15 (opens new short)
        assert result["campaigns_created"] == 2

    def test_short_round_trip(self, repository, mock_session):
        """Test sell->buy short round trip creates one campaign."""
        now = datetime.now(timezone.utc)
        sell = make_fill(1, "AAPL", "sell", 10, 160.0, now)
        buy = make_fill(2, "AAPL", "buy", 10, 150.0, now + timedelta(hours=1))

        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_session.query.return_value.outerjoin.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
            sell, buy,
        ]

        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        result = repository.rebuild_campaigns(account_id=1, symbol="AAPL", strategy_id=None)

        assert result["campaigns_created"] == 1
        assert result["fills_grouped"] == 2

    def test_deletes_existing_campaigns_before_rebuild(self, repository, mock_session):
        """Test that existing campaigns are deleted before rebuilding."""
        existing_campaign = MagicMock(spec=CampaignModel)
        existing_campaign.id = 99

        # First call: filter for existing campaigns returns one
        # Second call: outerjoin for fills returns empty
        mock_session.query.return_value.filter.return_value.all.side_effect = [
            [existing_campaign],  # existing campaigns query
        ]
        mock_session.query.return_value.outerjoin.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []

        repository.rebuild_campaigns(account_id=1, symbol="AAPL", strategy_id=None)

        # Verify delete was called on existing campaign
        mock_session.delete.assert_called_once_with(existing_campaign)


class TestEnsureDecisionContexts:
    """Tests for _ensure_decision_contexts method."""

    def test_creates_contexts_for_fills_without_one(self, repository, mock_session):
        """Test that fills without a decision context get one created."""
        now = datetime.now(timezone.utc)
        buy_fill = make_fill(1, "AAPL", "buy", 10, 150.0, now)
        sell_fill = make_fill(2, "AAPL", "sell", 10, 160.0, now + timedelta(hours=1))

        # Mock: outerjoin query returns fills without DC
        mock_session.query.return_value.outerjoin.return_value.filter.return_value.all.return_value = [
            buy_fill, sell_fill,
        ]

        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        created = repository._ensure_decision_contexts(account_id=1)

        assert created == 2
        contexts = [o for o in added_objects if isinstance(o, DecisionContextModel)]
        assert len(contexts) == 2
        # Buy fill should get "entry" context_type
        assert contexts[0].context_type == "entry"
        assert contexts[0].fill_id == 1
        # Sell fill should get "exit" context_type
        assert contexts[1].context_type == "exit"
        assert contexts[1].fill_id == 2

    def test_returns_zero_when_all_fills_have_contexts(self, repository, mock_session):
        """Test that zero is returned when all fills already have contexts."""
        mock_session.query.return_value.outerjoin.return_value.filter.return_value.all.return_value = []

        created = repository._ensure_decision_contexts(account_id=1)

        assert created == 0


class TestOnStrategyUpdated:
    """Tests for on_strategy_updated method."""

    def test_rebuilds_both_old_and_new_strategy_groups(self, repository, mock_session):
        """Test that both old and new strategy groups are rebuilt."""
        fill = make_fill(1, "AAPL", "buy", 10, 150.0, datetime.now(timezone.utc))

        # Mock fill lookup
        mock_session.query.return_value.filter.return_value.first.return_value = fill

        with patch.object(repository, "rebuild_campaigns") as mock_rebuild:
            mock_rebuild.return_value = {"campaigns_created": 0, "fills_grouped": 0}

            repository.on_strategy_updated(
                account_id=1,
                fill_id=1,
                old_strategy_id=10,
                new_strategy_id=20,
            )

        # Should rebuild for old strategy and new strategy
        assert mock_rebuild.call_count == 2
        calls = mock_rebuild.call_args_list
        assert calls[0] == ((1, "AAPL", 10),)
        assert calls[1] == ((1, "AAPL", 20),)

    def test_handles_none_to_strategy(self, repository, mock_session):
        """Test assigning a strategy to an untagged fill."""
        fill = make_fill(1, "AAPL", "buy", 10, 150.0, datetime.now(timezone.utc))
        mock_session.query.return_value.filter.return_value.first.return_value = fill

        with patch.object(repository, "rebuild_campaigns") as mock_rebuild:
            mock_rebuild.return_value = {"campaigns_created": 0, "fills_grouped": 0}

            repository.on_strategy_updated(
                account_id=1,
                fill_id=1,
                old_strategy_id=None,
                new_strategy_id=5,
            )

        # Should rebuild for None group and for strategy 5
        assert mock_rebuild.call_count == 2

    def test_does_nothing_when_fill_not_found(self, repository, mock_session):
        """Test that nothing happens when fill doesn't exist."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with patch.object(repository, "rebuild_campaigns") as mock_rebuild:
            repository.on_strategy_updated(
                account_id=1,
                fill_id=999,
                old_strategy_id=None,
                new_strategy_id=5,
            )

        mock_rebuild.assert_not_called()


class TestDecisionContextOperations:
    """Tests for decision context CRUD operations."""

    def test_create_decision_context(self, repository, mock_session):
        """Test creating a decision context."""
        mock_session.add.return_value = None
        mock_session.flush.return_value = None

        result = repository.create_decision_context(
            fill_id=1,
            account_id=1,
            context_type="entry",
            hypothesis="Breakout above resistance",
        )

        mock_session.add.assert_called_once()
        added = mock_session.add.call_args[0][0]
        assert added.fill_id == 1
        assert added.context_type == "entry"
        assert added.hypothesis == "Breakout above resistance"

    def test_get_or_create_returns_existing(self, repository, mock_session):
        """Test that get_or_create returns existing context."""
        existing = MagicMock(spec=DecisionContextModel)
        existing.id = 42
        existing.fill_id = 1
        mock_session.query.return_value.filter.return_value.first.return_value = existing

        result = repository.get_or_create_decision_context(
            fill_id=1,
            account_id=1,
        )

        assert result.id == 42
        mock_session.add.assert_not_called()

    def test_get_or_create_creates_new(self, repository, mock_session):
        """Test that get_or_create creates context when none exists."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_session.add.return_value = None
        mock_session.flush.return_value = None

        result = repository.get_or_create_decision_context(
            fill_id=1,
            account_id=1,
            context_type="entry",
        )

        mock_session.add.assert_called_once()


class TestCampaignQueries:
    """Tests for campaign query operations."""

    def test_get_campaigns_filters_by_account(self, repository, mock_session):
        """Test that get_campaigns filters by account_id."""
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        repository.get_campaigns(account_id=1)

        # Verify query was called (basic smoke test)
        mock_session.query.assert_called()

    def test_get_campaign_returns_none_when_not_found(self, repository, mock_session):
        """Test that get_campaign returns None for non-existent ID."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = repository.get_campaign(campaign_id=999)

        assert result is None

    def test_get_campaign_fills_joins_through_junction(self, repository, mock_session):
        """Test that get_campaign_fills queries through campaign_fills junction."""
        mock_session.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = []

        repository.get_campaign_fills(campaign_id=1)

        # Verify query was called with join
        mock_session.query.assert_called()


class TestSitePrefsModel:
    """Tests for UserProfile.site_prefs JSONB column and property accessors."""

    def test_site_pref_defaults_dict(self):
        """Test that SITE_PREF_DEFAULTS has the expected keys and values."""
        defaults = UserProfileModel.SITE_PREF_DEFAULTS
        assert defaults["theme"] == "light"
        assert defaults["sidebar_collapsed"] is False
        assert defaults["notifications_enabled"] is True
        assert defaults["language"] == "en"

    def test_site_prefs_property_defaults_when_none(self):
        """Test property accessors return defaults when site_prefs is None."""
        profile = UserProfileModel(
            user_account_id=1,
            profile=dict(UserProfileModel.PROFILE_DEFAULTS),
            risk_profile=dict(UserProfileModel.RISK_PROFILE_DEFAULTS),
        )
        # site_prefs is None by default (nullable column)
        assert profile.site_prefs is None

        # Property accessors should return defaults
        assert profile.theme == "light"
        assert profile.sidebar_collapsed is False
        assert profile.notifications_enabled is True
        assert profile.language == "en"

    def test_site_prefs_property_reads_from_dict(self):
        """Test property accessors read from site_prefs dict when set."""
        profile = UserProfileModel(
            user_account_id=1,
            profile=dict(UserProfileModel.PROFILE_DEFAULTS),
            risk_profile=dict(UserProfileModel.RISK_PROFILE_DEFAULTS),
            site_prefs={
                "theme": "dark",
                "sidebar_collapsed": True,
                "notifications_enabled": False,
                "language": "es",
            },
        )
        assert profile.theme == "dark"
        assert profile.sidebar_collapsed is True
        assert profile.notifications_enabled is False
        assert profile.language == "es"

    def test_site_prefs_property_setter_initializes_from_none(self):
        """Test that setting a property when site_prefs is None initializes defaults."""
        profile = UserProfileModel(
            user_account_id=1,
            profile=dict(UserProfileModel.PROFILE_DEFAULTS),
            risk_profile=dict(UserProfileModel.RISK_PROFILE_DEFAULTS),
        )
        assert profile.site_prefs is None

        profile.theme = "dark"

        assert profile.site_prefs is not None
        assert profile.theme == "dark"
        # Other defaults should be present after initialization
        assert profile.sidebar_collapsed is False
        assert profile.notifications_enabled is True
        assert profile.language == "en"

    def test_site_prefs_property_setter_preserves_other_keys(self):
        """Test that setting one property preserves other site_prefs values."""
        profile = UserProfileModel(
            user_account_id=1,
            profile=dict(UserProfileModel.PROFILE_DEFAULTS),
            risk_profile=dict(UserProfileModel.RISK_PROFILE_DEFAULTS),
            site_prefs={
                "theme": "dark",
                "sidebar_collapsed": True,
                "notifications_enabled": False,
                "language": "fr",
            },
        )
        profile.language = "de"

        assert profile.language == "de"
        assert profile.theme == "dark"  # unchanged
        assert profile.sidebar_collapsed is True  # unchanged
        assert profile.notifications_enabled is False  # unchanged

    def test_site_prefs_partial_dict_returns_defaults_for_missing(self):
        """Test that partial site_prefs dict returns defaults for missing keys."""
        profile = UserProfileModel(
            user_account_id=1,
            profile=dict(UserProfileModel.PROFILE_DEFAULTS),
            risk_profile=dict(UserProfileModel.RISK_PROFILE_DEFAULTS),
            site_prefs={"theme": "dark"},
        )
        assert profile.theme == "dark"
        # Missing keys should return defaults
        assert profile.sidebar_collapsed is False
        assert profile.notifications_enabled is True
        assert profile.language == "en"


class TestCreateProfileWithSitePrefs:
    """Tests for create_profile with site_prefs parameter."""

    def test_create_profile_without_site_prefs(self, repository, mock_session):
        """Test creating a profile without site_prefs passes None."""
        mock_session.add.return_value = None
        mock_session.flush.return_value = None

        repository.create_profile(account_id=1)

        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.site_prefs is None

    def test_create_profile_with_site_prefs_dict(self, repository, mock_session):
        """Test creating a profile with site_prefs structured dict."""
        mock_session.add.return_value = None
        mock_session.flush.return_value = None

        repository.create_profile(
            account_id=1,
            site_prefs={"theme": "dark", "language": "fr"},
        )

        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.site_prefs is not None
        assert added_obj.site_prefs["theme"] == "dark"
        assert added_obj.site_prefs["language"] == "fr"
        # Defaults should be merged in
        assert added_obj.site_prefs["sidebar_collapsed"] is False
        assert added_obj.site_prefs["notifications_enabled"] is True

    def test_create_profile_with_flat_site_pref_kwargs(self, repository, mock_session):
        """Test creating a profile with flat site_pref kwargs."""
        mock_session.add.return_value = None
        mock_session.flush.return_value = None

        repository.create_profile(
            account_id=1,
            theme="dark",
            sidebar_collapsed=True,
        )

        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.site_prefs is not None
        assert added_obj.site_prefs["theme"] == "dark"
        assert added_obj.site_prefs["sidebar_collapsed"] is True


class TestUpdateProfileWithSitePrefs:
    """Tests for update_profile with site_prefs parameter."""

    def test_update_profile_with_site_prefs_dict(self, repository, mock_session):
        """Test updating profile with site_prefs structured dict."""
        existing = UserProfileModel(
            user_account_id=1,
            profile=dict(UserProfileModel.PROFILE_DEFAULTS),
            risk_profile=dict(UserProfileModel.RISK_PROFILE_DEFAULTS),
            site_prefs={"theme": "light", "sidebar_collapsed": False,
                        "notifications_enabled": True, "language": "en"},
        )
        existing.id = 1

        with patch.object(repository, "get_profile", return_value=existing):
            result = repository.update_profile(
                account_id=1,
                site_prefs={"theme": "dark"},
            )

        assert result is not None
        assert result.site_prefs["theme"] == "dark"
        # Other values should be preserved
        assert result.site_prefs["sidebar_collapsed"] is False
        assert result.site_prefs["language"] == "en"

    def test_update_profile_with_flat_site_pref_kwargs(self, repository, mock_session):
        """Test updating profile with flat site_pref kwargs."""
        existing = UserProfileModel(
            user_account_id=1,
            profile=dict(UserProfileModel.PROFILE_DEFAULTS),
            risk_profile=dict(UserProfileModel.RISK_PROFILE_DEFAULTS),
            site_prefs=None,
        )
        existing.id = 1

        with patch.object(repository, "get_profile", return_value=existing):
            result = repository.update_profile(
                account_id=1,
                theme="dark",
                notifications_enabled=False,
            )

        assert result is not None
        assert result.site_prefs["theme"] == "dark"
        assert result.site_prefs["notifications_enabled"] is False
        # Defaults should be applied for unset keys
        assert result.site_prefs["sidebar_collapsed"] is False
        assert result.site_prefs["language"] == "en"

    def test_update_profile_site_prefs_does_not_affect_other_fields(self, repository, mock_session):
        """Test that updating site_prefs does not affect profile or risk_profile."""
        original_profile = dict(UserProfileModel.PROFILE_DEFAULTS)
        original_risk = dict(UserProfileModel.RISK_PROFILE_DEFAULTS)
        existing = UserProfileModel(
            user_account_id=1,
            profile=original_profile,
            risk_profile=original_risk,
            site_prefs={"theme": "light", "sidebar_collapsed": False,
                        "notifications_enabled": True, "language": "en"},
        )
        existing.id = 1

        with patch.object(repository, "get_profile", return_value=existing):
            result = repository.update_profile(
                account_id=1,
                site_prefs={"theme": "dark"},
            )

        assert result.profile == original_profile
        assert result.risk_profile == original_risk


class TestCreateStrategyWithRiskProfile:
    """Tests for create_strategy with risk_profile parameter."""

    def test_create_strategy_without_risk_profile(self, repository, mock_session):
        """Test creating a strategy with no risk_profile passes None."""
        with patch.object(repository, "create_strategy", wraps=repository.create_strategy):
            strategy = StrategyModel(
                account_id=1,
                name="Scalping",
                description="Quick scalp trades",
            )
            mock_session.add.return_value = None
            mock_session.flush.return_value = None

            # Call the actual method (it calls session.add + flush)
            result = repository.create_strategy(
                account_id=1,
                name="Scalping",
                description="Quick scalp trades",
            )

            # Verify session.add was called with the model
            mock_session.add.assert_called_once()
            added_obj = mock_session.add.call_args[0][0]
            assert added_obj.name == "Scalping"
            assert added_obj.risk_profile is None

    def test_create_strategy_with_risk_profile(self, repository, mock_session):
        """Test creating a strategy with risk_profile overrides."""
        risk_overrides = {
            "max_position_size_pct": 2.5,
            "max_risk_per_trade_pct": 0.5,
        }

        mock_session.add.return_value = None
        mock_session.flush.return_value = None

        result = repository.create_strategy(
            account_id=1,
            name="Scalping",
            description="Quick scalp trades",
            risk_profile=risk_overrides,
        )

        # Verify the model was created with risk_profile set
        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.risk_profile == risk_overrides
        assert added_obj.risk_profile["max_position_size_pct"] == 2.5
        assert added_obj.risk_profile["max_risk_per_trade_pct"] == 0.5


class TestBuildEvaluatorConfigsWithStrategy:
    """Tests for build_evaluator_configs with strategy_id parameter."""

    def _make_mock_profile(self):
        """Create a mock UserProfile with standard defaults."""
        profile = MagicMock(spec=UserProfileModel)
        profile.account_balance = 10000.0
        profile.max_position_size_pct = 5.0
        profile.max_risk_per_trade_pct = 1.0
        profile.min_risk_reward_ratio = 2.0
        return profile

    def test_build_configs_without_strategy(self, repository):
        """Test that configs use profile defaults when no strategy is given."""
        mock_account = MagicMock()
        mock_account.id = 1
        mock_profile = self._make_mock_profile()

        with patch.object(repository, "get_account", return_value=mock_account):
            with patch.object(repository, "get_or_create_profile", return_value=mock_profile):
                with patch.object(repository, "get_user_rules", return_value=[]):
                    configs = repository.build_evaluator_configs(account_id=1)

        # Default evaluators should be created
        assert "risk_reward" in configs
        assert "exit_plan" in configs

        # Verify profile defaults are used
        rr_config = configs["risk_reward"]
        assert rr_config.custom_params["max_position_size_pct"] == 5.0
        assert rr_config.custom_params["max_risk_per_trade_pct"] == 1.0
        assert rr_config.custom_params["min_rr_ratio"] == 2.0

    def test_build_configs_with_strategy_risk_overrides(self, repository):
        """Test that strategy risk_profile overrides user profile defaults."""
        mock_account = MagicMock()
        mock_account.id = 1
        mock_profile = self._make_mock_profile()

        mock_strategy = MagicMock(spec=StrategyModel)
        mock_strategy.id = 10
        mock_strategy.risk_profile = {
            "max_position_size_pct": 2.5,
            "max_risk_per_trade_pct": 0.5,
        }

        with patch.object(repository, "get_account", return_value=mock_account):
            with patch.object(repository, "get_or_create_profile", return_value=mock_profile):
                with patch.object(repository, "get_user_rules", return_value=[]):
                    with patch.object(repository, "get_strategy", return_value=mock_strategy):
                        configs = repository.build_evaluator_configs(
                            account_id=1,
                            strategy_id=10,
                        )

        # Strategy overrides should be applied
        rr_config = configs["risk_reward"]
        assert rr_config.custom_params["max_position_size_pct"] == 2.5
        assert rr_config.custom_params["max_risk_per_trade_pct"] == 0.5
        # Non-overridden values should remain from profile
        assert rr_config.custom_params["min_rr_ratio"] == 2.0
        assert rr_config.custom_params["account_balance"] == 10000.0

    def test_build_configs_strategy_with_no_risk_profile(self, repository):
        """Test that strategy with null risk_profile does not modify defaults."""
        mock_account = MagicMock()
        mock_account.id = 1
        mock_profile = self._make_mock_profile()

        mock_strategy = MagicMock(spec=StrategyModel)
        mock_strategy.id = 10
        mock_strategy.risk_profile = None

        with patch.object(repository, "get_account", return_value=mock_account):
            with patch.object(repository, "get_or_create_profile", return_value=mock_profile):
                with patch.object(repository, "get_user_rules", return_value=[]):
                    with patch.object(repository, "get_strategy", return_value=mock_strategy):
                        configs = repository.build_evaluator_configs(
                            account_id=1,
                            strategy_id=10,
                        )

        # Profile defaults should remain unchanged
        rr_config = configs["risk_reward"]
        assert rr_config.custom_params["max_position_size_pct"] == 5.0
        assert rr_config.custom_params["max_risk_per_trade_pct"] == 1.0

    def test_build_configs_strategy_not_found(self, repository):
        """Test that non-existent strategy_id gracefully falls back to defaults."""
        mock_account = MagicMock()
        mock_account.id = 1
        mock_profile = self._make_mock_profile()

        with patch.object(repository, "get_account", return_value=mock_account):
            with patch.object(repository, "get_or_create_profile", return_value=mock_profile):
                with patch.object(repository, "get_user_rules", return_value=[]):
                    with patch.object(repository, "get_strategy", return_value=None):
                        configs = repository.build_evaluator_configs(
                            account_id=1,
                            strategy_id=999,
                        )

        # Profile defaults should remain unchanged
        rr_config = configs["risk_reward"]
        assert rr_config.custom_params["max_position_size_pct"] == 5.0

    def test_build_configs_strategy_min_rr_override(self, repository):
        """Test that min_risk_reward_ratio maps correctly to min_rr_ratio."""
        mock_account = MagicMock()
        mock_account.id = 1
        mock_profile = self._make_mock_profile()

        mock_strategy = MagicMock(spec=StrategyModel)
        mock_strategy.id = 10
        mock_strategy.risk_profile = {
            "min_risk_reward_ratio": 3.0,
        }

        with patch.object(repository, "get_account", return_value=mock_account):
            with patch.object(repository, "get_or_create_profile", return_value=mock_profile):
                with patch.object(repository, "get_user_rules", return_value=[]):
                    with patch.object(repository, "get_strategy", return_value=mock_strategy):
                        configs = repository.build_evaluator_configs(
                            account_id=1,
                            strategy_id=10,
                        )

        # min_risk_reward_ratio should map to min_rr_ratio in base_params
        rr_config = configs["risk_reward"]
        assert rr_config.custom_params["min_rr_ratio"] == 3.0

    def test_build_configs_strategy_overrides_applied_to_all_evaluators(self, repository):
        """Test that strategy overrides propagate to all evaluator configs."""
        mock_account = MagicMock()
        mock_account.id = 1
        mock_profile = self._make_mock_profile()

        mock_strategy = MagicMock(spec=StrategyModel)
        mock_strategy.id = 10
        mock_strategy.risk_profile = {
            "max_position_size_pct": 1.0,
        }

        with patch.object(repository, "get_account", return_value=mock_account):
            with patch.object(repository, "get_or_create_profile", return_value=mock_profile):
                with patch.object(repository, "get_user_rules", return_value=[]):
                    with patch.object(repository, "get_strategy", return_value=mock_strategy):
                        configs = repository.build_evaluator_configs(
                            account_id=1,
                            strategy_id=10,
                        )

        # Both default evaluators should have the override
        assert configs["risk_reward"].custom_params["max_position_size_pct"] == 1.0
        assert configs["exit_plan"].custom_params["max_position_size_pct"] == 1.0
