"""Unit tests for TradingBuddyRepository campaign population.

Tests the populate_campaigns_from_fills functionality that matches
buys/sells into position lots, closures, and campaigns.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.data.database.trading_repository import TradingBuddyRepository
from src.data.database.broker_models import TradeFill as TradeFillModel
from src.data.database.trade_lifecycle_models import (
    PositionLot as PositionLotModel,
    LotClosure as LotClosureModel,
    PositionCampaign as PositionCampaignModel,
    CampaignLeg as CampaignLegModel,
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


def make_lot(
    id: int,
    symbol: str,
    direction: str,
    open_qty: float,
    remaining_qty: float,
    avg_open_price: float,
    opened_at: datetime,
    open_fill_id: int,
    account_id: int = 1,
    status: str = "open",
) -> PositionLotModel:
    """Create a mock PositionLotModel."""
    lot = MagicMock(spec=PositionLotModel)
    lot.id = id
    lot.symbol = symbol
    lot.direction = direction
    lot.open_qty = open_qty
    lot.remaining_qty = remaining_qty
    lot.avg_open_price = avg_open_price
    lot.opened_at = opened_at
    lot.open_fill_id = open_fill_id
    lot.account_id = account_id
    lot.status = status
    return lot


class TestGetProcessedFillIds:
    """Tests for get_processed_fill_ids method."""

    def test_returns_empty_set_when_no_lots(self, repository, mock_session):
        """Test that empty set is returned when no lots exist."""
        mock_session.query.return_value.filter.return_value.all.return_value = []

        result = repository.get_processed_fill_ids(account_id=1)

        assert result == set()

    def test_returns_fill_ids_from_lots(self, repository, mock_session):
        """Test that fill IDs from position lots are returned."""
        mock_session.query.return_value.filter.return_value.all.return_value = [
            (101,),
            (102,),
            (103,),
        ]

        result = repository.get_processed_fill_ids(account_id=1)

        assert result == {101, 102, 103}


class TestGetUnprocessedFills:
    """Tests for get_unprocessed_fills method."""

    def test_returns_fills_not_in_lots(self, repository, mock_session):
        """Test that fills not in lots are returned."""
        now = datetime.now(timezone.utc)

        # Setup mocks
        fill1 = make_fill(1, "AAPL", "buy", 10, 150.0, now)
        fill2 = make_fill(2, "AAPL", "sell", 10, 155.0, now + timedelta(hours=1))

        # Mock get_processed_fill_ids to return empty (no processed fills)
        mock_session.query.return_value.filter.return_value.all.return_value = []

        # Mock the query for unprocessed fills
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            fill1,
            fill2,
        ]

        # Mock the closure query
        mock_session.query.return_value.join.return_value.filter.return_value.all.return_value = []

        result = repository.get_unprocessed_fills(account_id=1)

        assert len(result) == 2


class TestPopulateCampaignsFromFills:
    """Tests for populate_campaigns_from_fills method."""

    def test_returns_zero_stats_when_no_fills(self, repository, mock_session):
        """Test that empty stats are returned when no fills exist."""
        # Mock empty fills query
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = repository.populate_campaigns_from_fills(account_id=1)

        assert result["lots_created"] == 0
        assert result["closures_created"] == 0
        assert result["campaigns_created"] == 0
        assert result["fills_processed"] == 0

    def test_creates_campaign_for_simple_round_trip(self, repository, mock_session):
        """Test that a simple buy->sell creates a campaign."""
        now = datetime.now(timezone.utc)
        account_id = 1

        # Create fills: BUY 10 AAPL @ 150, SELL 10 AAPL @ 160
        buy_fill = make_fill(1, "AAPL", "buy", 10, 150.0, now)
        sell_fill = make_fill(2, "AAPL", "sell", 10, 160.0, now + timedelta(hours=1))

        # Setup mock query responses
        # 1. All fills query
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            buy_fill,
            sell_fill,
        ]

        # 2. Get processed fill IDs (none processed yet)
        mock_session.query.return_value.filter.return_value.all.return_value = []

        # 3. Closure fill IDs (none yet)
        mock_session.query.return_value.join.return_value.filter.return_value.all.return_value = []

        # 4. Get open lots (none yet)
        mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []

        # Track created objects
        created_campaigns = []
        created_lots = []
        created_closures = []
        created_legs = []
        created_leg_fill_maps = []

        # Lot ID counter
        lot_id = [0]
        closure_id = [0]
        campaign_id = [0]
        leg_id = [0]

        def mock_add(obj):
            if hasattr(obj, "__tablename__"):
                if obj.__tablename__ == "position_campaigns":
                    campaign_id[0] += 1
                    obj.id = campaign_id[0]
                    created_campaigns.append(obj)
                elif obj.__tablename__ == "position_lots":
                    lot_id[0] += 1
                    obj.id = lot_id[0]
                    created_lots.append(obj)
                elif obj.__tablename__ == "lot_closures":
                    closure_id[0] += 1
                    obj.id = closure_id[0]
                    created_closures.append(obj)
                elif obj.__tablename__ == "campaign_legs":
                    leg_id[0] += 1
                    obj.id = leg_id[0]
                    created_legs.append(obj)
                elif obj.__tablename__ == "leg_fill_map":
                    created_leg_fill_maps.append(obj)

        mock_session.add.side_effect = mock_add

        # Need to patch the repository methods that are being called
        with patch.object(repository, "get_open_lots", return_value=[]):
            with patch.object(repository, "create_campaign") as mock_create_campaign:
                with patch.object(repository, "create_lot") as mock_create_lot:
                    with patch.object(repository, "create_closure") as mock_create_closure:
                        with patch.object(repository, "update_lot_remaining_qty") as mock_update_lot:
                            with patch.object(repository, "create_leg") as mock_create_leg:
                                with patch.object(repository, "create_leg_fill_map") as mock_create_lfm:
                                    # Setup mocks to return proper objects
                                    mock_campaign = MagicMock()
                                    mock_campaign.id = 1
                                    mock_create_campaign.return_value = mock_campaign

                                    mock_lot = MagicMock()
                                    mock_lot.id = 1
                                    mock_lot.open_qty = 10
                                    mock_lot.remaining_qty = 10
                                    mock_lot.avg_open_price = 150.0
                                    mock_lot.opened_at = now
                                    mock_lot.open_fill_id = 1
                                    mock_create_lot.return_value = mock_lot

                                    mock_closure = MagicMock()
                                    mock_closure.id = 1
                                    mock_closure.matched_qty = 10
                                    mock_closure.close_price = 160.0
                                    mock_closure.realized_pnl = 100.0
                                    mock_closure.close_fill_id = 2
                                    mock_create_closure.return_value = mock_closure

                                    mock_leg = MagicMock()
                                    mock_leg.id = 1
                                    mock_create_leg.return_value = mock_leg

                                    result = repository.populate_campaigns_from_fills(account_id=account_id)

        # Verify stats
        assert result["campaigns_created"] == 1
        assert result["lots_created"] == 1
        assert result["closures_created"] == 1
        assert result["fills_processed"] == 2


class TestProcessSymbolFills:
    """Tests for _process_symbol_fills method."""

    def test_buy_creates_long_lot(self, repository, mock_session):
        """Test that a buy creates a long lot."""
        now = datetime.now(timezone.utc)
        buy_fill = make_fill(1, "AAPL", "buy", 10, 150.0, now)

        with patch.object(repository, "get_open_lots", return_value=[]):
            with patch.object(repository, "create_campaign") as mock_create_campaign:
                with patch.object(repository, "create_lot") as mock_create_lot:
                    mock_campaign = MagicMock()
                    mock_campaign.id = 1
                    mock_create_campaign.return_value = mock_campaign

                    mock_lot = MagicMock()
                    mock_lot.id = 1
                    mock_lot.remaining_qty = 10
                    mock_create_lot.return_value = mock_lot

                    stats = repository._process_symbol_fills(
                        account_id=1,
                        symbol="AAPL",
                        fills=[buy_fill],
                        processed_fill_ids=set(),
                    )

        assert stats["lots_created"] == 1
        mock_create_lot.assert_called_once()
        call_kwargs = mock_create_lot.call_args.kwargs
        assert call_kwargs["direction"] == "long"
        assert call_kwargs["open_qty"] == 10
        assert call_kwargs["avg_open_price"] == 150.0

    def test_sell_creates_short_lot(self, repository, mock_session):
        """Test that a sell creates a short lot."""
        now = datetime.now(timezone.utc)
        sell_fill = make_fill(1, "AAPL", "sell", 10, 150.0, now)

        with patch.object(repository, "get_open_lots", return_value=[]):
            with patch.object(repository, "create_campaign") as mock_create_campaign:
                with patch.object(repository, "create_lot") as mock_create_lot:
                    mock_campaign = MagicMock()
                    mock_campaign.id = 1
                    mock_create_campaign.return_value = mock_campaign

                    mock_lot = MagicMock()
                    mock_lot.id = 1
                    mock_lot.remaining_qty = 10
                    mock_create_lot.return_value = mock_lot

                    stats = repository._process_symbol_fills(
                        account_id=1,
                        symbol="AAPL",
                        fills=[sell_fill],
                        processed_fill_ids=set(),
                    )

        assert stats["lots_created"] == 1
        mock_create_lot.assert_called_once()
        call_kwargs = mock_create_lot.call_args.kwargs
        assert call_kwargs["direction"] == "short"

    def test_sell_closes_long_lot(self, repository, mock_session):
        """Test that a sell closes an open long lot."""
        now = datetime.now(timezone.utc)
        buy_fill = make_fill(1, "AAPL", "buy", 10, 150.0, now)
        sell_fill = make_fill(2, "AAPL", "sell", 10, 160.0, now + timedelta(hours=1))

        with patch.object(repository, "get_open_lots", return_value=[]):
            with patch.object(repository, "create_campaign") as mock_create_campaign:
                with patch.object(repository, "create_lot") as mock_create_lot:
                    with patch.object(repository, "create_closure") as mock_create_closure:
                        with patch.object(repository, "update_lot_remaining_qty"):
                            with patch.object(repository, "create_leg") as mock_create_leg:
                                with patch.object(repository, "create_leg_fill_map"):
                                    mock_campaign = MagicMock()
                                    mock_campaign.id = 1
                                    mock_create_campaign.return_value = mock_campaign

                                    mock_lot = MagicMock()
                                    mock_lot.id = 1
                                    mock_lot.open_qty = 10
                                    mock_lot.remaining_qty = 10
                                    mock_lot.avg_open_price = 150.0
                                    mock_lot.opened_at = now
                                    mock_lot.open_fill_id = 1
                                    mock_create_lot.return_value = mock_lot

                                    mock_closure = MagicMock()
                                    mock_closure.id = 1
                                    mock_closure.matched_qty = 10
                                    mock_closure.close_price = 160.0
                                    mock_closure.realized_pnl = 100.0  # (160-150)*10
                                    mock_closure.close_fill_id = 2
                                    mock_create_closure.return_value = mock_closure

                                    mock_leg = MagicMock()
                                    mock_leg.id = 1
                                    mock_create_leg.return_value = mock_leg

                                    stats = repository._process_symbol_fills(
                                        account_id=1,
                                        symbol="AAPL",
                                        fills=[buy_fill, sell_fill],
                                        processed_fill_ids=set(),
                                    )

        assert stats["lots_created"] == 1
        assert stats["closures_created"] == 1
        assert stats["campaigns_created"] == 1

        # Verify closure was created with correct P&L
        mock_create_closure.assert_called_once()
        call_kwargs = mock_create_closure.call_args.kwargs
        assert call_kwargs["realized_pnl"] == 100.0  # (160-150)*10
        assert call_kwargs["matched_qty"] == 10

    def test_buy_closes_short_lot(self, repository, mock_session):
        """Test that a buy closes an open short lot."""
        now = datetime.now(timezone.utc)
        sell_fill = make_fill(1, "AAPL", "sell", 10, 160.0, now)
        buy_fill = make_fill(2, "AAPL", "buy", 10, 150.0, now + timedelta(hours=1))

        with patch.object(repository, "get_open_lots", return_value=[]):
            with patch.object(repository, "create_campaign") as mock_create_campaign:
                with patch.object(repository, "create_lot") as mock_create_lot:
                    with patch.object(repository, "create_closure") as mock_create_closure:
                        with patch.object(repository, "update_lot_remaining_qty"):
                            with patch.object(repository, "create_leg") as mock_create_leg:
                                with patch.object(repository, "create_leg_fill_map"):
                                    mock_campaign = MagicMock()
                                    mock_campaign.id = 1
                                    mock_create_campaign.return_value = mock_campaign

                                    mock_lot = MagicMock()
                                    mock_lot.id = 1
                                    mock_lot.open_qty = 10
                                    mock_lot.remaining_qty = 10
                                    mock_lot.avg_open_price = 160.0
                                    mock_lot.opened_at = now
                                    mock_lot.open_fill_id = 1
                                    mock_create_lot.return_value = mock_lot

                                    mock_closure = MagicMock()
                                    mock_closure.id = 1
                                    mock_closure.matched_qty = 10
                                    mock_closure.close_price = 150.0
                                    mock_closure.realized_pnl = 100.0  # (160-150)*10 for short
                                    mock_closure.close_fill_id = 2
                                    mock_create_closure.return_value = mock_closure

                                    mock_leg = MagicMock()
                                    mock_leg.id = 1
                                    mock_create_leg.return_value = mock_leg

                                    stats = repository._process_symbol_fills(
                                        account_id=1,
                                        symbol="AAPL",
                                        fills=[sell_fill, buy_fill],
                                        processed_fill_ids=set(),
                                    )

        assert stats["closures_created"] == 1

        # Verify short P&L: (open_price - close_price) * qty = (160-150)*10 = 100
        mock_create_closure.assert_called_once()
        call_kwargs = mock_create_closure.call_args.kwargs
        assert call_kwargs["realized_pnl"] == 100.0

    def test_skips_already_processed_fills(self, repository, mock_session):
        """Test that already processed fills are skipped."""
        now = datetime.now(timezone.utc)
        buy_fill = make_fill(1, "AAPL", "buy", 10, 150.0, now)

        with patch.object(repository, "get_open_lots", return_value=[]):
            with patch.object(repository, "create_campaign") as mock_create_campaign:
                with patch.object(repository, "create_lot") as mock_create_lot:
                    stats = repository._process_symbol_fills(
                        account_id=1,
                        symbol="AAPL",
                        fills=[buy_fill],
                        processed_fill_ids={1},  # Fill 1 already processed
                    )

        assert stats["lots_created"] == 0
        assert stats["fills_processed"] == 0
        mock_create_lot.assert_not_called()
        mock_create_campaign.assert_not_called()

    def test_partial_close_leaves_remaining_qty(self, repository, mock_session):
        """Test partial close leaves remaining quantity in lot."""
        now = datetime.now(timezone.utc)
        buy_fill = make_fill(1, "AAPL", "buy", 10, 150.0, now)
        sell_fill = make_fill(2, "AAPL", "sell", 5, 160.0, now + timedelta(hours=1))

        with patch.object(repository, "get_open_lots", return_value=[]):
            with patch.object(repository, "create_campaign") as mock_create_campaign:
                with patch.object(repository, "create_lot") as mock_create_lot:
                    with patch.object(repository, "create_closure") as mock_create_closure:
                        with patch.object(repository, "update_lot_remaining_qty") as mock_update_qty:
                            mock_campaign = MagicMock()
                            mock_campaign.id = 1
                            mock_create_campaign.return_value = mock_campaign

                            mock_lot = MagicMock()
                            mock_lot.id = 1
                            mock_lot.open_qty = 10
                            mock_lot.remaining_qty = 10
                            mock_lot.avg_open_price = 150.0
                            mock_lot.opened_at = now
                            mock_lot.open_fill_id = 1
                            mock_create_lot.return_value = mock_lot

                            mock_closure = MagicMock()
                            mock_closure.id = 1
                            mock_closure.matched_qty = 5
                            mock_closure.close_price = 160.0
                            mock_closure.realized_pnl = 50.0  # (160-150)*5
                            mock_closure.close_fill_id = 2
                            mock_create_closure.return_value = mock_closure

                            stats = repository._process_symbol_fills(
                                account_id=1,
                                symbol="AAPL",
                                fills=[buy_fill, sell_fill],
                                processed_fill_ids=set(),
                            )

        assert stats["closures_created"] == 1
        # Verify lot was updated with remaining qty of 5
        mock_update_qty.assert_called_once_with(1, 5)


class TestFinalizeCampaign:
    """Tests for _finalize_campaign method."""

    def test_computes_total_pnl(self, repository, mock_session):
        """Test that total P&L is computed from closures."""
        now = datetime.now(timezone.utc)

        campaign = MagicMock()
        campaign.id = 1
        campaign.symbol = "AAPL"

        lots = [
            make_lot(1, "AAPL", "long", 10, 0, 150.0, now, 1),
        ]

        closures = [MagicMock()]
        closures[0].realized_pnl = 100.0
        closures[0].matched_qty = 10
        closures[0].close_price = 160.0
        closures[0].close_fill_id = 2

        fills = [
            make_fill(1, "AAPL", "buy", 10, 150.0, now),
            make_fill(2, "AAPL", "sell", 10, 160.0, now + timedelta(hours=1)),
        ]

        repository._finalize_campaign(campaign, lots, closures, fills)

        assert campaign.realized_pnl == 100.0
        assert campaign.status == "closed"

    def test_computes_return_percentage(self, repository, mock_session):
        """Test that return percentage is computed correctly."""
        now = datetime.now(timezone.utc)

        campaign = MagicMock()
        campaign.id = 1
        campaign.symbol = "AAPL"

        lots = [
            make_lot(1, "AAPL", "long", 10, 0, 100.0, now, 1),
        ]

        closures = [MagicMock()]
        closures[0].realized_pnl = 100.0  # 10% return on 1000 cost basis
        closures[0].matched_qty = 10
        closures[0].close_price = 110.0
        closures[0].close_fill_id = 2

        fills = [
            make_fill(1, "AAPL", "buy", 10, 100.0, now),
            make_fill(2, "AAPL", "sell", 10, 110.0, now + timedelta(hours=1)),
        ]

        repository._finalize_campaign(campaign, lots, closures, fills)

        # Return = 100 / 1000 * 100 = 10%
        assert campaign.return_pct == 10.0

    def test_computes_holding_period(self, repository, mock_session):
        """Test that holding period is computed correctly."""
        now = datetime.now(timezone.utc)

        campaign = MagicMock()
        campaign.id = 1
        campaign.symbol = "AAPL"

        lots = [
            make_lot(1, "AAPL", "long", 10, 0, 150.0, now, 1),
        ]

        closures = [MagicMock()]
        closures[0].realized_pnl = 100.0
        closures[0].matched_qty = 10
        closures[0].close_price = 160.0
        closures[0].close_fill_id = 2

        fills = [
            make_fill(1, "AAPL", "buy", 10, 150.0, now),
            make_fill(2, "AAPL", "sell", 10, 160.0, now + timedelta(hours=2)),
        ]

        repository._finalize_campaign(campaign, lots, closures, fills)

        # 2 hours = 7200 seconds
        assert campaign.holding_period_sec == 7200


class TestPopulateLegsFromCampaigns:
    """Tests for populate_legs_from_campaigns method."""

    def test_returns_zero_stats_when_campaign_not_found(self, repository, mock_session):
        """Test that zero stats are returned when campaign doesn't exist."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = repository.populate_legs_from_campaigns(campaign_id=999)

        assert result["legs_created"] == 0
        assert result["fill_maps_created"] == 0

    def test_creates_open_and_close_legs_for_simple_round_trip(self, repository, mock_session):
        """Test that open and close legs are created for a simple buy->sell."""
        now = datetime.now(timezone.utc)

        # Create mock campaign
        mock_campaign = MagicMock()
        mock_campaign.id = 1
        mock_campaign.direction = "long"

        # Create mock lot
        mock_lot = make_lot(
            id=1, symbol="AAPL", direction="long",
            open_qty=10, remaining_qty=0, avg_open_price=150.0,
            opened_at=now, open_fill_id=1,
        )
        mock_lot.campaign_id = 1

        # Create mock closure
        mock_closure = MagicMock()
        mock_closure.id = 1
        mock_closure.lot_id = 1
        mock_closure.matched_qty = 10
        mock_closure.close_price = 160.0
        mock_closure.close_fill_id = 2

        # Create mock fills
        buy_fill = make_fill(1, "AAPL", "buy", 10, 150.0, now)
        sell_fill = make_fill(2, "AAPL", "sell", 10, 160.0, now + timedelta(hours=1))

        with patch.object(repository, "get_campaign", return_value=mock_campaign):
            with patch.object(repository, "get_closures_for_lot", return_value=[mock_closure]):
                with patch.object(repository, "get_legs_for_campaign", return_value=[]):
                    with patch.object(repository, "create_leg") as mock_create_leg:
                        with patch.object(repository, "create_leg_fill_map") as mock_create_lfm:
                            # Mock the lots query
                            mock_session.query.return_value.filter.return_value.all.return_value = [mock_lot]
                            # Mock the fills query
                            mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
                                buy_fill, sell_fill
                            ]

                            mock_leg = MagicMock()
                            mock_leg.id = 1
                            mock_create_leg.return_value = mock_leg

                            result = repository.populate_legs_from_campaigns(campaign_id=1)

        assert result["legs_created"] == 2
        assert result["fill_maps_created"] == 2

        # Verify leg types
        leg_calls = mock_create_leg.call_args_list
        assert len(leg_calls) == 2
        assert leg_calls[0].kwargs["leg_type"] == "open"
        assert leg_calls[0].kwargs["side"] == "buy"
        assert leg_calls[1].kwargs["leg_type"] == "close"
        assert leg_calls[1].kwargs["side"] == "sell"


class TestDetermineLegType:
    """Tests for _determine_leg_type method."""

    def test_flat_to_long_is_open(self, repository):
        """Test that going from flat to long is an 'open' leg."""
        leg_type = repository._determine_leg_type(
            prev_position=0.0,
            new_position=10.0,
            is_buy=True,
            campaign_direction="long",
        )
        assert leg_type == "open"

    def test_flat_to_short_is_open(self, repository):
        """Test that going from flat to short is an 'open' leg."""
        leg_type = repository._determine_leg_type(
            prev_position=0.0,
            new_position=-10.0,
            is_buy=False,
            campaign_direction="short",
        )
        assert leg_type == "open"

    def test_long_to_flat_is_close(self, repository):
        """Test that going from long to flat is a 'close' leg."""
        leg_type = repository._determine_leg_type(
            prev_position=10.0,
            new_position=0.0,
            is_buy=False,
            campaign_direction="long",
        )
        assert leg_type == "close"

    def test_short_to_flat_is_close(self, repository):
        """Test that going from short to flat is a 'close' leg."""
        leg_type = repository._determine_leg_type(
            prev_position=-10.0,
            new_position=0.0,
            is_buy=True,
            campaign_direction="short",
        )
        assert leg_type == "close"

    def test_increasing_long_is_add(self, repository):
        """Test that adding to a long position is an 'add' leg."""
        leg_type = repository._determine_leg_type(
            prev_position=10.0,
            new_position=20.0,
            is_buy=True,
            campaign_direction="long",
        )
        assert leg_type == "add"

    def test_increasing_short_is_add(self, repository):
        """Test that adding to a short position is an 'add' leg."""
        leg_type = repository._determine_leg_type(
            prev_position=-10.0,
            new_position=-20.0,
            is_buy=False,
            campaign_direction="short",
        )
        assert leg_type == "add"

    def test_decreasing_long_is_reduce(self, repository):
        """Test that reducing a long position is a 'reduce' leg."""
        leg_type = repository._determine_leg_type(
            prev_position=20.0,
            new_position=10.0,
            is_buy=False,
            campaign_direction="long",
        )
        assert leg_type == "reduce"

    def test_decreasing_short_is_reduce(self, repository):
        """Test that reducing a short position is a 'reduce' leg."""
        leg_type = repository._determine_leg_type(
            prev_position=-20.0,
            new_position=-10.0,
            is_buy=True,
            campaign_direction="short",
        )
        assert leg_type == "reduce"

    def test_flip_long_to_short_is_flip_open(self, repository):
        """Test that flipping from long to short creates a flip_open leg."""
        leg_type = repository._determine_leg_type(
            prev_position=10.0,
            new_position=-5.0,
            is_buy=False,
            campaign_direction="long",
        )
        assert leg_type == "flip_open"

    def test_flip_short_to_long_is_flip_open(self, repository):
        """Test that flipping from short to long creates a flip_open leg."""
        leg_type = repository._determine_leg_type(
            prev_position=-10.0,
            new_position=5.0,
            is_buy=True,
            campaign_direction="short",
        )
        assert leg_type == "flip_open"


class TestPopulateCampaignsAndLegs:
    """Tests for populate_campaigns_and_legs orchestrator method."""

    def test_returns_stats_with_total_pnl(self, repository, mock_session):
        """Test that populate_campaigns_and_legs returns stats with total_pnl."""
        # Mock populate_campaigns_from_fills to return some stats
        with patch.object(repository, "populate_campaigns_from_fills") as mock_populate:
            mock_populate.return_value = {
                "lots_created": 2,
                "closures_created": 2,
                "campaigns_created": 1,
                "legs_created": 2,
                "fills_processed": 4,
            }

            # Mock get_campaigns to return a closed campaign with realized_pnl
            mock_campaign = MagicMock()
            mock_campaign.status = "closed"
            mock_campaign.realized_pnl = 150.0

            with patch.object(repository, "get_campaigns") as mock_get_campaigns:
                mock_get_campaigns.return_value = [mock_campaign]

                result = repository.populate_campaigns_and_legs(account_id=1)

        assert result["campaigns_created"] == 1
        assert result["lots_created"] == 2
        assert result["legs_created"] == 2
        assert result["total_pnl"] == 150.0

    def test_total_pnl_sums_multiple_campaigns(self, repository, mock_session):
        """Test that total_pnl sums P&L from multiple closed campaigns."""
        with patch.object(repository, "populate_campaigns_from_fills") as mock_populate:
            mock_populate.return_value = {
                "lots_created": 4,
                "closures_created": 4,
                "campaigns_created": 2,
                "legs_created": 4,
                "fills_processed": 8,
            }

            # Mock two closed campaigns
            mock_campaign1 = MagicMock()
            mock_campaign1.status = "closed"
            mock_campaign1.realized_pnl = 100.0

            mock_campaign2 = MagicMock()
            mock_campaign2.status = "closed"
            mock_campaign2.realized_pnl = 50.0

            with patch.object(repository, "get_campaigns") as mock_get_campaigns:
                mock_get_campaigns.return_value = [mock_campaign1, mock_campaign2]

                result = repository.populate_campaigns_and_legs(account_id=1)

        assert result["total_pnl"] == 150.0

    def test_excludes_open_campaigns_from_total_pnl(self, repository, mock_session):
        """Test that open campaigns are excluded from total_pnl calculation."""
        with patch.object(repository, "populate_campaigns_from_fills") as mock_populate:
            mock_populate.return_value = {
                "lots_created": 2,
                "closures_created": 1,
                "campaigns_created": 2,
                "legs_created": 2,
                "fills_processed": 4,
            }

            # Mock one closed and one open campaign
            mock_closed = MagicMock()
            mock_closed.status = "closed"
            mock_closed.realized_pnl = 100.0

            mock_open = MagicMock()
            mock_open.status = "open"
            mock_open.realized_pnl = None  # Open campaigns don't have realized_pnl

            with patch.object(repository, "get_campaigns") as mock_get_campaigns:
                mock_get_campaigns.return_value = [mock_closed, mock_open]

                result = repository.populate_campaigns_and_legs(account_id=1)

        # Only the closed campaign's P&L should be counted
        assert result["total_pnl"] == 100.0


class TestComputeLegTypes:
    """Tests for _compute_leg_types method."""

    def test_simple_open_close_long(self, repository):
        """Test open/close legs for a simple long position."""
        now = datetime.now(timezone.utc)

        buy_fill = make_fill(1, "AAPL", "buy", 10, 150.0, now)
        sell_fill = make_fill(2, "AAPL", "sell", 10, 160.0, now + timedelta(hours=1))

        mock_lot = MagicMock()
        mock_lot.open_qty = 10
        mock_lot.avg_open_price = 150.0

        mock_closure = MagicMock()
        mock_closure.matched_qty = 10
        mock_closure.close_price = 160.0

        legs = repository._compute_leg_types(
            fills=[buy_fill, sell_fill],
            lot_by_open_fill={1: mock_lot},
            closures_by_close_fill={2: [mock_closure]},
            campaign_direction="long",
        )

        assert len(legs) == 2
        assert legs[0]["leg_type"] == "open"
        assert legs[0]["side"] == "buy"
        assert legs[0]["quantity"] == 10
        assert legs[1]["leg_type"] == "close"
        assert legs[1]["side"] == "sell"
        assert legs[1]["quantity"] == 10

    def test_scale_in_creates_add_leg(self, repository):
        """Test that scale-in creates an 'add' leg."""
        now = datetime.now(timezone.utc)

        buy1 = make_fill(1, "AAPL", "buy", 5, 150.0, now)
        buy2 = make_fill(2, "AAPL", "buy", 5, 152.0, now + timedelta(hours=1))
        sell_fill = make_fill(3, "AAPL", "sell", 10, 160.0, now + timedelta(hours=2))

        mock_lot1 = MagicMock()
        mock_lot1.open_qty = 5
        mock_lot1.avg_open_price = 150.0

        mock_lot2 = MagicMock()
        mock_lot2.open_qty = 5
        mock_lot2.avg_open_price = 152.0

        mock_closure1 = MagicMock()
        mock_closure1.matched_qty = 5
        mock_closure1.close_price = 160.0

        mock_closure2 = MagicMock()
        mock_closure2.matched_qty = 5
        mock_closure2.close_price = 160.0

        legs = repository._compute_leg_types(
            fills=[buy1, buy2, sell_fill],
            lot_by_open_fill={1: mock_lot1, 2: mock_lot2},
            closures_by_close_fill={3: [mock_closure1, mock_closure2]},
            campaign_direction="long",
        )

        assert len(legs) == 3
        assert legs[0]["leg_type"] == "open"
        assert legs[0]["side"] == "buy"
        assert legs[1]["leg_type"] == "add"
        assert legs[1]["side"] == "buy"
        assert legs[2]["leg_type"] == "close"
        assert legs[2]["side"] == "sell"

    def test_scale_out_creates_reduce_and_close_legs(self, repository):
        """Test that scale-out creates 'reduce' then 'close' legs."""
        now = datetime.now(timezone.utc)

        buy_fill = make_fill(1, "AAPL", "buy", 10, 150.0, now)
        sell1 = make_fill(2, "AAPL", "sell", 5, 160.0, now + timedelta(hours=1))
        sell2 = make_fill(3, "AAPL", "sell", 5, 165.0, now + timedelta(hours=2))

        mock_lot = MagicMock()
        mock_lot.open_qty = 10
        mock_lot.avg_open_price = 150.0

        mock_closure1 = MagicMock()
        mock_closure1.matched_qty = 5
        mock_closure1.close_price = 160.0

        mock_closure2 = MagicMock()
        mock_closure2.matched_qty = 5
        mock_closure2.close_price = 165.0

        legs = repository._compute_leg_types(
            fills=[buy_fill, sell1, sell2],
            lot_by_open_fill={1: mock_lot},
            closures_by_close_fill={2: [mock_closure1], 3: [mock_closure2]},
            campaign_direction="long",
        )

        assert len(legs) == 3
        assert legs[0]["leg_type"] == "open"
        assert legs[1]["leg_type"] == "reduce"
        assert legs[2]["leg_type"] == "close"

    def test_short_position_legs(self, repository):
        """Test leg types for a short position round trip."""
        now = datetime.now(timezone.utc)

        sell_fill = make_fill(1, "AAPL", "sell", 10, 160.0, now)
        buy_fill = make_fill(2, "AAPL", "buy", 10, 150.0, now + timedelta(hours=1))

        mock_lot = MagicMock()
        mock_lot.open_qty = 10
        mock_lot.avg_open_price = 160.0

        mock_closure = MagicMock()
        mock_closure.matched_qty = 10
        mock_closure.close_price = 150.0

        legs = repository._compute_leg_types(
            fills=[sell_fill, buy_fill],
            lot_by_open_fill={1: mock_lot},
            closures_by_close_fill={2: [mock_closure]},
            campaign_direction="short",
        )

        assert len(legs) == 2
        assert legs[0]["leg_type"] == "open"
        assert legs[0]["side"] == "sell"
        assert legs[1]["leg_type"] == "close"
        assert legs[1]["side"] == "buy"
