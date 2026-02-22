package dataclient

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/protobuf/types/known/timestamppb"

	pb "github.com/algomatic/marketdata-service/proto/gen/go/market/v1"
	"github.com/algomatic/marketdata-service/internal/db"
)

// Client wraps the gRPC MarketDataService client.
// It provides the same interface as db.Client for use in the service layer.
type Client struct {
	conn   *grpc.ClientConn
	market pb.MarketDataServiceClient
	logger *slog.Logger
}

// NewClient connects to the data-service gRPC server.
func NewClient(ctx context.Context, target string, logger *slog.Logger) (*Client, error) {
	if logger == nil {
		logger = slog.Default()
	}

	conn, err := grpc.NewClient(target, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, fmt.Errorf("connecting to data-service at %s: %w", target, err)
	}

	logger.Info("Connected to data-service", "target", target)
	return &Client{
		conn:   conn,
		market: pb.NewMarketDataServiceClient(conn),
		logger: logger,
	}, nil
}

// Close shuts down the gRPC connection.
func (c *Client) Close() {
	if c.conn != nil {
		c.conn.Close()
		c.logger.Info("Data-service connection closed")
	}
}

// HealthCheck verifies connectivity to the data-service.
func (c *Client) HealthCheck(ctx context.Context) error {
	_, err := c.market.ListTickers(ctx, &pb.ListTickersRequest{ActiveOnly: true})
	return err
}

// GetOrCreateTicker returns the ticker ID and asset class for the given symbol, creating if needed.
func (c *Client) GetOrCreateTicker(ctx context.Context, symbol string) (db.TickerInfo, error) {
	resp, err := c.market.GetOrCreateTicker(ctx, &pb.GetOrCreateTickerRequest{Symbol: symbol})
	if err != nil {
		return db.TickerInfo{}, fmt.Errorf("get_or_create_ticker %q: %w", symbol, err)
	}
	assetClass := resp.Ticker.AssetClass
	if assetClass == "" {
		assetClass = "stock"
	}
	return db.TickerInfo{
		ID:         int(resp.Ticker.Id),
		AssetClass: assetClass,
	}, nil
}

// GetActiveTickers returns all active ticker symbols ordered alphabetically.
func (c *Client) GetActiveTickers(ctx context.Context) ([]string, error) {
	resp, err := c.market.ListTickers(ctx, &pb.ListTickersRequest{ActiveOnly: true})
	if err != nil {
		return nil, fmt.Errorf("listing active tickers: %w", err)
	}
	symbols := make([]string, len(resp.Tickers))
	for i, t := range resp.Tickers {
		symbols[i] = t.Symbol
	}
	return symbols, nil
}

// GetLatestTimestamp returns the most recent bar timestamp for a ticker/timeframe.
func (c *Client) GetLatestTimestamp(ctx context.Context, tickerID int, timeframe string) (*time.Time, error) {
	resp, err := c.market.GetLatestTimestamp(ctx, &pb.GetLatestTimestampRequest{
		TickerId:  int32(tickerID),
		Timeframe: timeframe,
	})
	if err != nil {
		return nil, fmt.Errorf("getting latest timestamp: %w", err)
	}
	if resp.Timestamp == nil {
		return nil, nil
	}
	ts := resp.Timestamp.AsTime()
	return &ts, nil
}

// GetBars1Min returns 1Min bars for a ticker after the given timestamp, ordered ascending.
func (c *Client) GetBars1Min(ctx context.Context, tickerID int, after time.Time) ([]db.OHLCVBar, error) {
	// Use GetBars with start = after + 1 nanosecond (to match "timestamp > after").
	start := after.Add(time.Nanosecond)
	var bars []db.OHLCVBar
	pageToken := ""

	for {
		req := &pb.GetBarsRequest{
			TickerId:  int32(tickerID),
			Timeframe: "1Min",
			Start:     timestamppb.New(start),
			PageSize:  2000,
			PageToken: pageToken,
		}
		resp, err := c.market.GetBars(ctx, req)
		if err != nil {
			return nil, fmt.Errorf("getting 1Min bars: %w", err)
		}

		for _, b := range resp.Bars {
			bars = append(bars, pbBarToDbBar(b))
		}

		if resp.NextPageToken == "" {
			break
		}
		pageToken = resp.NextPageToken
	}

	return bars, nil
}

// BulkInsertBars inserts OHLCV bars via gRPC. Chunks into 1000-bar RPCs.
func (c *Client) BulkInsertBars(ctx context.Context, tickerID int, timeframe, source string, bars []db.OHLCVBar) (int, error) {
	if len(bars) == 0 {
		return 0, nil
	}

	const chunkSize = 1000
	totalInserted := 0

	for i := 0; i < len(bars); i += chunkSize {
		end := i + chunkSize
		if end > len(bars) {
			end = len(bars)
		}
		chunk := bars[i:end]

		pbBars := make([]*pb.OHLCVBar, len(chunk))
		for j, b := range chunk {
			pbBars[j] = dbBarToPb(b)
		}

		resp, err := c.market.BulkInsertBars(ctx, &pb.BulkInsertBarsRequest{
			TickerId:  int32(tickerID),
			Timeframe: timeframe,
			Source:    source,
			Bars:      pbBars,
		})
		if err != nil {
			return totalInserted, fmt.Errorf("bulk inserting bars: %w", err)
		}
		totalInserted += int(resp.RowsInserted)
	}

	return totalInserted, nil
}

// UpdateSyncLog upserts a data_sync_log entry via gRPC.
func (c *Client) UpdateSyncLog(ctx context.Context, entry db.SyncLogEntry) error {
	req := &pb.UpdateSyncLogRequest{
		TickerId:    int32(entry.TickerID),
		Timeframe:   entry.Timeframe,
		BarsFetched: int32(entry.BarsFetched),
		Status:      entry.Status,
	}

	if entry.LastSyncedTimestamp != nil {
		req.LastSyncedTimestamp = timestamppb.New(*entry.LastSyncedTimestamp)
	}
	if entry.FirstSyncedTimestamp != nil {
		req.FirstSyncedTimestamp = timestamppb.New(*entry.FirstSyncedTimestamp)
	}
	if entry.ErrorMessage != nil {
		req.ErrorMessage = entry.ErrorMessage
	}

	_, err := c.market.UpdateSyncLog(ctx, req)
	if err != nil {
		return fmt.Errorf("updating sync log: %w", err)
	}
	return nil
}

// DeactivateTicker marks a ticker as inactive via gRPC BulkUpsertTickers.
func (c *Client) DeactivateTicker(ctx context.Context, symbol string) error {
	_, err := c.market.BulkUpsertTickers(ctx, &pb.BulkUpsertTickersRequest{
		Tickers: []*pb.Ticker{
			{Symbol: symbol, IsActive: false},
		},
	})
	if err != nil {
		return fmt.Errorf("deactivating ticker %q: %w", symbol, err)
	}
	c.logger.Info("Deactivated ticker", "symbol", symbol)
	return nil
}

func pbBarToDbBar(b *pb.OHLCVBar) db.OHLCVBar {
	bar := db.OHLCVBar{
		Timestamp: b.Timestamp.AsTime(),
		Open:      b.Open,
		High:      b.High,
		Low:       b.Low,
		Close:     b.Close,
		Volume:    b.Volume,
		Source:    b.Source,
	}
	if b.TradeCount != nil {
		tc := int(*b.TradeCount)
		bar.TradeCount = &tc
	}
	return bar
}

func dbBarToPb(b db.OHLCVBar) *pb.OHLCVBar {
	bar := &pb.OHLCVBar{
		Timestamp: timestamppb.New(b.Timestamp),
		Open:      b.Open,
		High:      b.High,
		Low:       b.Low,
		Close:     b.Close,
		Volume:    b.Volume,
		Source:    b.Source,
	}
	if b.TradeCount != nil {
		tc := int32(*b.TradeCount)
		bar.TradeCount = &tc
	}
	return bar
}
