package server

import (
	"context"
	"log/slog"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/timestamppb"

	"github.com/algomatic/data-service/internal/repository"
	pb "github.com/algomatic/data-service/proto/gen/go/probe/v1"
)

// ProbeServer implements the ProbeDataService gRPC service.
type ProbeServer struct {
	pb.UnimplementedProbeDataServiceServer
	strategies *repository.ProbeStrategyRepo
	results    *repository.ProbeResultRepo
	trades     *repository.ProbeTradeRepo
	logger     *slog.Logger
}

// NewProbeServer creates a new ProbeServer.
func NewProbeServer(
	strategies *repository.ProbeStrategyRepo,
	results *repository.ProbeResultRepo,
	trades *repository.ProbeTradeRepo,
	logger *slog.Logger,
) *ProbeServer {
	return &ProbeServer{
		strategies: strategies,
		results:    results,
		trades:     trades,
		logger:     logger,
	}
}

// LookupStrategyID returns the database ID for a strategy by name.
func (s *ProbeServer) LookupStrategyID(ctx context.Context, req *pb.LookupStrategyIDRequest) (*pb.LookupStrategyIDResponse, error) {
	if req.Name == "" {
		return nil, status.Error(codes.InvalidArgument, "name is required")
	}

	id, found, err := s.strategies.LookupByName(ctx, req.Name)
	if err != nil {
		s.logger.Error("LookupStrategyID failed", "name", req.Name, "error", err)
		return nil, status.Errorf(codes.Internal, "lookup failed: %v", err)
	}

	return &pb.LookupStrategyIDResponse{
		StrategyId: id,
		Found:      found,
	}, nil
}

// SaveResults inserts aggregated probe results into strategy_probe_results.
func (s *ProbeServer) SaveResults(ctx context.Context, req *pb.SaveResultsRequest) (*pb.SaveResultsResponse, error) {
	if len(req.Results) == 0 {
		return &pb.SaveResultsResponse{Inserted: 0, Total: 0}, nil
	}

	// Convert proto messages to repository structs
	repoResults := make([]repository.ProbeResult, len(req.Results))
	for i, r := range req.Results {
		openDay, err := time.Parse("2006-01-02", r.OpenDay)
		if err != nil {
			return nil, status.Errorf(codes.InvalidArgument, "invalid open_day %q at index %d: %v", r.OpenDay, i, err)
		}

		repoResults[i] = repository.ProbeResult{
			RunID:       r.RunId,
			Symbol:      r.Symbol,
			StrategyID:  r.StrategyId,
			PeriodStart: r.PeriodStart.AsTime(),
			PeriodEnd:   r.PeriodEnd.AsTime(),
			Timeframe:   r.Timeframe,
			RiskProfile: r.RiskProfile,
			OpenDay:     openDay,
			OpenHour:    r.OpenHour,
			LongShort:   r.LongShort,
			NumTrades:   r.NumTrades,
			PnLMean:     r.PnlMean,
			PnLStd:      r.PnlStd,
			MaxDrawdown: r.MaxDrawdown,
			MaxProfit:   r.MaxProfit,
		}
	}

	mappings, inserted, err := s.results.SaveResults(ctx, repoResults)
	if err != nil {
		s.logger.Error("SaveResults failed", "error", err)
		return nil, status.Errorf(codes.Internal, "save failed: %v", err)
	}

	// Convert mappings to proto
	pbMappings := make([]*pb.ResultIdMapping, len(mappings))
	for i, m := range mappings {
		pbMappings[i] = &pb.ResultIdMapping{
			OpenDay:   m.Key.OpenDay,
			OpenHour:  m.Key.OpenHour,
			LongShort: m.Key.LongShort,
			ResultId:  m.ResultID,
		}
	}

	return &pb.SaveResultsResponse{
		Inserted: int32(inserted),
		Total:    int32(len(req.Results)),
		Mappings: pbMappings,
	}, nil
}

// SaveTrades bulk-inserts individual trade records into strategy_probe_trades.
func (s *ProbeServer) SaveTrades(ctx context.Context, req *pb.SaveTradesRequest) (*pb.SaveTradesResponse, error) {
	if len(req.Trades) == 0 {
		return &pb.SaveTradesResponse{Inserted: 0}, nil
	}

	// Convert proto messages to repository structs
	repoTrades := make([]repository.ProbeTrade, len(req.Trades))
	for i, t := range req.Trades {
		repoTrades[i] = repository.ProbeTrade{
			ResultID:           t.ResultId,
			Ticker:             t.Ticker,
			OpenTimestamp:      t.OpenTimestamp.AsTime(),
			CloseTimestamp:     t.CloseTimestamp.AsTime(),
			Direction:          t.Direction,
			OpenJustification:  t.OpenJustification,
			CloseJustification: t.CloseJustification,
			PnL:                t.Pnl,
			PnLPct:             t.PnlPct,
			BarsHeld:           t.BarsHeld,
			MaxDrawdown:        t.MaxDrawdown,
			MaxProfit:          t.MaxProfit,
			PnLStd:             t.PnlStd,
		}
	}

	count, err := s.trades.SaveTrades(ctx, repoTrades)
	if err != nil {
		s.logger.Error("SaveTrades failed", "error", err)
		return nil, status.Errorf(codes.Internal, "save failed: %v", err)
	}

	return &pb.SaveTradesResponse{
		Inserted: int32(count),
	}, nil
}

// Compile-time check that ProbeServer implements the interface.
var _ pb.ProbeDataServiceServer = (*ProbeServer)(nil)

// Unused but needed to suppress the "unused import" for timestamppb in case
// the compiler is aggressive. The import is used in SaveResults for AsTime().
var _ = timestamppb.Now
