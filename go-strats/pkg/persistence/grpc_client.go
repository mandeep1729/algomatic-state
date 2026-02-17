package persistence

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/protobuf/types/known/timestamppb"

	"github.com/algomatic/strats100/go-strats/pkg/types"

	pb "github.com/algomatic/data-service/proto/gen/go/probe/v1"
)

// GRPCClient provides database persistence operations via the data-service gRPC API.
// This replaces direct pgx database access in Client.
type GRPCClient struct {
	conn   *grpc.ClientConn
	client pb.ProbeDataServiceClient
	logger *slog.Logger
}

// NewGRPCClient creates a new gRPC persistence client connected to the data-service.
func NewGRPCClient(ctx context.Context, addr string, logger *slog.Logger) (*GRPCClient, error) {
	if logger == nil {
		logger = slog.Default()
	}

	conn, err := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, fmt.Errorf("connecting to data-service at %s: %w", addr, err)
	}

	client := pb.NewProbeDataServiceClient(conn)
	logger.Info("Connected to data-service via gRPC", "addr", addr)

	return &GRPCClient{conn: conn, client: client, logger: logger}, nil
}

// Close shuts down the gRPC connection.
func (c *GRPCClient) Close() error {
	c.logger.Info("Closing gRPC connection to data-service")
	return c.conn.Close()
}

// LookupStrategyID looks up the probe_strategies.id for a given strategy name.
// Returns 0 if the strategy is not found.
func (c *GRPCClient) LookupStrategyID(ctx context.Context, name string) (int, error) {
	resp, err := c.client.LookupStrategyID(ctx, &pb.LookupStrategyIDRequest{Name: name})
	if err != nil {
		return 0, fmt.Errorf("looking up strategy %q: %w", name, err)
	}
	if !resp.Found {
		return 0, nil
	}
	return int(resp.StrategyId), nil
}

// SaveResults inserts aggregated results via gRPC.
// Returns a map of GroupKey -> result_id for linking trades, and the count of rows inserted.
func (c *GRPCClient) SaveResults(ctx context.Context, results []AggregatedResult) (map[GroupKey]int64, int, error) {
	if len(results) == 0 {
		return nil, 0, nil
	}

	pbResults := make([]*pb.AggregatedResult, len(results))
	for i, r := range results {
		pbResults[i] = &pb.AggregatedResult{
			RunId:       r.RunID,
			Symbol:      r.Symbol,
			StrategyId:  int32(r.StrategyID),
			PeriodStart: timestamppb.New(r.PeriodStart),
			PeriodEnd:   timestamppb.New(r.PeriodEnd),
			Timeframe:   r.Timeframe,
			RiskProfile: r.RiskProfile,
			OpenDay:     r.OpenDay.Format("2006-01-02"),
			OpenHour:    int32(r.OpenHour),
			LongShort:   r.LongShort,
			NumTrades:   int32(r.NumTrades),
			PnlMean:     r.PnLMean,
			PnlStd:      r.PnLStd,
			MaxDrawdown: r.MaxDrawdown,
			MaxProfit:   r.MaxProfit,
		}
	}

	resp, err := c.client.SaveResults(ctx, &pb.SaveResultsRequest{Results: pbResults})
	if err != nil {
		return nil, 0, fmt.Errorf("saving results via gRPC: %w", err)
	}

	resultIDMap := make(map[GroupKey]int64, len(resp.Mappings))
	for _, m := range resp.Mappings {
		openDay, parseErr := time.Parse("2006-01-02", m.OpenDay)
		if parseErr != nil {
			c.logger.Warn("Could not parse open_day from mapping", "open_day", m.OpenDay, "error", parseErr)
			continue
		}
		key := GroupKey{
			OpenDay:   openDay,
			OpenHour:  int(m.OpenHour),
			LongShort: m.LongShort,
		}
		resultIDMap[key] = m.ResultId
	}

	c.logger.Info("Saved aggregated results via gRPC",
		"inserted", resp.Inserted,
		"total", resp.Total,
	)
	return resultIDMap, int(resp.Inserted), nil
}

// SaveTrades inserts individual trade records via gRPC.
func (c *GRPCClient) SaveTrades(ctx context.Context, trades []TradeRecord) (int, error) {
	if len(trades) == 0 {
		return 0, nil
	}

	pbTrades := make([]*pb.TradeRecord, len(trades))
	for i, t := range trades {
		pbTrades[i] = &pb.TradeRecord{
			ResultId:           t.ResultID,
			Ticker:             t.Ticker,
			OpenTimestamp:      timestamppb.New(t.OpenTimestamp),
			CloseTimestamp:     timestamppb.New(t.CloseTimestamp),
			Direction:          t.Direction,
			OpenJustification:  t.OpenJustification,
			CloseJustification: t.CloseJustification,
			Pnl:                t.PnL,
			PnlPct:             t.PnLPct,
			BarsHeld:           int32(t.BarsHeld),
			MaxDrawdown:        t.MaxDrawdown,
			MaxProfit:          t.MaxProfit,
			PnlStd:             t.PnLStd,
		}
	}

	resp, err := c.client.SaveTrades(ctx, &pb.SaveTradesRequest{Trades: pbTrades})
	if err != nil {
		return 0, fmt.Errorf("saving trades via gRPC: %w", err)
	}

	c.logger.Info("Saved trade records via gRPC", "count", resp.Inserted)
	return int(resp.Inserted), nil
}

// Persist saves both aggregated results and individual trades via gRPC.
// This is the high-level entry point matching Client.Persist.
func (c *GRPCClient) Persist(
	ctx context.Context,
	trades []TradeRecord,
	engineTrades []types.Trade,
	results []AggregatedResult,
	persistTrades bool,
) (resultCount, tradeCount int, err error) {
	resultIDMap, resultCount, err := c.SaveResults(ctx, results)
	if err != nil {
		return 0, 0, fmt.Errorf("saving results: %w", err)
	}

	if !persistTrades || len(trades) == 0 {
		return resultCount, 0, nil
	}

	// Link trades to results (same logic as Client.Persist)
	matched, unmatched := MapTradesToResults(trades, engineTrades, resultIDMap)
	if unmatched > 0 {
		c.logger.Warn("Some trades could not be linked to result rows",
			"unmatched", unmatched,
			"total", len(trades),
		)
	}

	tradeCount, err = c.SaveTrades(ctx, matched)
	if err != nil {
		return resultCount, 0, fmt.Errorf("saving trades: %w", err)
	}

	return resultCount, tradeCount, nil
}

// Compile-time check that GRPCClient implements Persister.
var _ Persister = (*GRPCClient)(nil)
