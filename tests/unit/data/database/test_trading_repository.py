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
