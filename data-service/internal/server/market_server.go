package server

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/timestamppb"

	"github.com/jackc/pgx/v5"

	pb "github.com/algomatic/data-service/proto/gen/go/market/v1"
	"github.com/algomatic/data-service/internal/repository"
)

// MarketServer implements the MarketDataService gRPC server.
type MarketServer struct {
	pb.UnimplementedMarketDataServiceServer
	tickers  *repository.TickerRepo
	bars     *repository.BarRepo
	features *repository.FeatureRepo
	syncLogs *repository.SyncLogRepo
	logger   *slog.Logger
}

// NewMarketServer creates a new MarketServer with the given repositories.
func NewMarketServer(
	tickers *repository.TickerRepo,
	bars *repository.BarRepo,
	features *repository.FeatureRepo,
	syncLogs *repository.SyncLogRepo,
	logger *slog.Logger,
) *MarketServer {
	return &MarketServer{
		tickers:  tickers,
		bars:     bars,
		features: features,
		syncLogs: syncLogs,
		logger:   logger,
	}
}

// mapError converts repository errors to gRPC status codes.
func mapError(err error, msg string) error {
	if err == nil {
		return nil
	}
	if err == pgx.ErrNoRows {
		return status.Errorf(codes.NotFound, "%s: not found", msg)
	}
	if err == context.Canceled {
		return status.Errorf(codes.Canceled, "%s: canceled", msg)
	}
	// Check for invalid argument (our repos return errors with this prefix).
	if errMsg := err.Error(); len(errMsg) > 0 {
		if contains(errMsg, "invalid timeframe") {
			return status.Errorf(codes.InvalidArgument, "%s: %v", msg, err)
		}
	}
	return status.Errorf(codes.Internal, "%s", msg)
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > 0 && containsStr(s, substr))
}

func containsStr(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

func tsPtr(ts *timestamppb.Timestamp) *time.Time {
	if ts == nil {
		return nil
	}
	t := ts.AsTime()
	return &t
}

func tsToPb(t *time.Time) *timestamppb.Timestamp {
	if t == nil {
		return nil
	}
	return timestamppb.New(*t)
}

// --- Ticker RPCs ---

func (s *MarketServer) GetTicker(ctx context.Context, req *pb.GetTickerRequest) (*pb.GetTickerResponse, error) {
	if req.Symbol == "" {
		return nil, status.Error(codes.InvalidArgument, "symbol is required")
	}

	t, err := s.tickers.GetTicker(ctx, req.Symbol)
	if err != nil {
		s.logger.Error("GetTicker failed", "symbol", req.Symbol, "error", err)
		return nil, mapError(err, "GetTicker")
	}
	if t == nil {
		return nil, status.Errorf(codes.NotFound, "ticker %q not found", req.Symbol)
	}

	return &pb.GetTickerResponse{Ticker: tickerToProto(t)}, nil
}

func (s *MarketServer) ListTickers(ctx context.Context, req *pb.ListTickersRequest) (*pb.ListTickersResponse, error) {
	tickers, err := s.tickers.ListTickers(ctx, req.ActiveOnly)
	if err != nil {
		s.logger.Error("ListTickers failed", "error", err)
		return nil, mapError(err, "ListTickers")
	}

	result := make([]*pb.Ticker, len(tickers))
	for i := range tickers {
		result[i] = tickerToProto(&tickers[i])
	}
	return &pb.ListTickersResponse{Tickers: result}, nil
}

func (s *MarketServer) GetOrCreateTicker(ctx context.Context, req *pb.GetOrCreateTickerRequest) (*pb.GetOrCreateTickerResponse, error) {
	if req.Symbol == "" {
		return nil, status.Error(codes.InvalidArgument, "symbol is required")
	}

	t, created, err := s.tickers.GetOrCreateTicker(ctx, req.Symbol, req.Name, req.Exchange, req.AssetType, req.AssetClass)
	if err != nil {
		s.logger.Error("GetOrCreateTicker failed", "symbol", req.Symbol, "error", err)
		return nil, mapError(err, "GetOrCreateTicker")
	}

	return &pb.GetOrCreateTickerResponse{
		Ticker:  tickerToProto(t),
		Created: created,
	}, nil
}

func (s *MarketServer) BulkUpsertTickers(ctx context.Context, req *pb.BulkUpsertTickersRequest) (*pb.BulkUpsertTickersResponse, error) {
	tickers := make([]repository.Ticker, len(req.Tickers))
	for i, t := range req.Tickers {
		tickers[i] = repository.Ticker{
			Symbol:     t.Symbol,
			Name:       t.Name,
			Exchange:   t.Exchange,
			AssetType:  t.AssetType,
			AssetClass: t.AssetClass,
			IsActive:   t.IsActive,
		}
	}

	count, err := s.tickers.BulkUpsertTickers(ctx, tickers)
	if err != nil {
		s.logger.Error("BulkUpsertTickers failed", "error", err)
		return nil, mapError(err, "BulkUpsertTickers")
	}

	return &pb.BulkUpsertTickersResponse{UpsertedCount: int32(count)}, nil
}

// --- Bar RPCs ---

func (s *MarketServer) GetBars(ctx context.Context, req *pb.GetBarsRequest) (*pb.GetBarsResponse, error) {
	var pageToken *time.Time
	if req.PageToken != "" {
		t, err := time.Parse(time.RFC3339Nano, req.PageToken)
		if err != nil {
			return nil, status.Errorf(codes.InvalidArgument, "invalid page_token: %v", err)
		}
		pageToken = &t
	}

	bars, err := s.bars.GetBars(ctx, req.TickerId, req.Timeframe, tsPtr(req.Start), tsPtr(req.End), req.PageSize, pageToken)
	if err != nil {
		s.logger.Error("GetBars failed", "ticker_id", req.TickerId, "error", err)
		return nil, mapError(err, "GetBars")
	}

	result := make([]*pb.OHLCVBar, len(bars))
	var nextPageToken string
	for i := range bars {
		result[i] = barToProto(&bars[i])
	}
	if len(bars) > 0 && int32(len(bars)) == req.PageSize {
		nextPageToken = bars[len(bars)-1].Timestamp.Format(time.RFC3339Nano)
	}

	return &pb.GetBarsResponse{
		Bars:          result,
		NextPageToken: nextPageToken,
	}, nil
}

func (s *MarketServer) StreamBars(req *pb.StreamBarsRequest, stream pb.MarketDataService_StreamBarsServer) error {
	bars, err := s.bars.StreamBars(stream.Context(), req.TickerId, req.Timeframe, tsPtr(req.Start), tsPtr(req.End))
	if err != nil {
		s.logger.Error("StreamBars failed", "ticker_id", req.TickerId, "error", err)
		return mapError(err, "StreamBars")
	}

	for i := range bars {
		if err := stream.Send(barToProto(&bars[i])); err != nil {
			return err
		}
	}
	return nil
}

func (s *MarketServer) BulkInsertBars(ctx context.Context, req *pb.BulkInsertBarsRequest) (*pb.BulkInsertBarsResponse, error) {
	if len(req.Bars) > 1000 {
		return nil, status.Errorf(codes.InvalidArgument, "max 1000 bars per call, got %d", len(req.Bars))
	}

	bars := make([]repository.OHLCVBar, len(req.Bars))
	for i, b := range req.Bars {
		bars[i] = repository.OHLCVBar{
			Timestamp:  b.Timestamp.AsTime(),
			Open:       b.Open,
			High:       b.High,
			Low:        b.Low,
			Close:      b.Close,
			Volume:     b.Volume,
			TradeCount: b.TradeCount,
		}
	}

	inserted, err := s.bars.BulkInsertBars(ctx, req.TickerId, req.Timeframe, req.Source, bars)
	if err != nil {
		s.logger.Error("BulkInsertBars failed", "ticker_id", req.TickerId, "error", err)
		return nil, mapError(err, "BulkInsertBars")
	}

	return &pb.BulkInsertBarsResponse{RowsInserted: int32(inserted)}, nil
}

func (s *MarketServer) DeleteBars(ctx context.Context, req *pb.DeleteBarsRequest) (*pb.DeleteBarsResponse, error) {
	deleted, err := s.bars.DeleteBars(ctx, req.TickerId, req.Timeframe, tsPtr(req.Start), tsPtr(req.End))
	if err != nil {
		s.logger.Error("DeleteBars failed", "ticker_id", req.TickerId, "error", err)
		return nil, mapError(err, "DeleteBars")
	}

	return &pb.DeleteBarsResponse{RowsDeleted: int32(deleted)}, nil
}

func (s *MarketServer) GetLatestTimestamp(ctx context.Context, req *pb.GetLatestTimestampRequest) (*pb.GetLatestTimestampResponse, error) {
	ts, err := s.bars.GetLatestTimestamp(ctx, req.TickerId, req.Timeframe)
	if err != nil {
		s.logger.Error("GetLatestTimestamp failed", "ticker_id", req.TickerId, "error", err)
		return nil, mapError(err, "GetLatestTimestamp")
	}

	return &pb.GetLatestTimestampResponse{Timestamp: tsToPb(ts)}, nil
}

func (s *MarketServer) GetEarliestTimestamp(ctx context.Context, req *pb.GetEarliestTimestampRequest) (*pb.GetEarliestTimestampResponse, error) {
	ts, err := s.bars.GetEarliestTimestamp(ctx, req.TickerId, req.Timeframe)
	if err != nil {
		s.logger.Error("GetEarliestTimestamp failed", "ticker_id", req.TickerId, "error", err)
		return nil, mapError(err, "GetEarliestTimestamp")
	}

	return &pb.GetEarliestTimestampResponse{Timestamp: tsToPb(ts)}, nil
}

func (s *MarketServer) GetBarCount(ctx context.Context, req *pb.GetBarCountRequest) (*pb.GetBarCountResponse, error) {
	count, err := s.bars.GetBarCount(ctx, req.TickerId, req.Timeframe, tsPtr(req.Start), tsPtr(req.End))
	if err != nil {
		s.logger.Error("GetBarCount failed", "ticker_id", req.TickerId, "error", err)
		return nil, mapError(err, "GetBarCount")
	}

	return &pb.GetBarCountResponse{Count: count}, nil
}

func (s *MarketServer) GetBarIdsForTimestamps(ctx context.Context, req *pb.GetBarIdsForTimestampsRequest) (*pb.GetBarIdsForTimestampsResponse, error) {
	timestamps := make([]time.Time, len(req.Timestamps))
	for i, ts := range req.Timestamps {
		timestamps[i] = ts.AsTime()
	}

	result, err := s.bars.GetBarIdsForTimestamps(ctx, req.TickerId, req.Timeframe, timestamps)
	if err != nil {
		s.logger.Error("GetBarIdsForTimestamps failed", "ticker_id", req.TickerId, "error", err)
		return nil, mapError(err, "GetBarIdsForTimestamps")
	}

	tsToID := make(map[string]int64, len(result))
	for ts, id := range result {
		tsToID[ts.Format(time.RFC3339Nano)] = id
	}

	return &pb.GetBarIdsForTimestampsResponse{TimestampToId: tsToID}, nil
}

// --- Feature RPCs ---

func (s *MarketServer) GetFeatures(ctx context.Context, req *pb.GetFeaturesRequest) (*pb.GetFeaturesResponse, error) {
	var pageToken *time.Time
	if req.PageToken != "" {
		t, err := time.Parse(time.RFC3339Nano, req.PageToken)
		if err != nil {
			return nil, status.Errorf(codes.InvalidArgument, "invalid page_token: %v", err)
		}
		pageToken = &t
	}

	features, err := s.features.GetFeatures(ctx, req.TickerId, req.Timeframe, tsPtr(req.Start), tsPtr(req.End), req.PageSize, pageToken)
	if err != nil {
		s.logger.Error("GetFeatures failed", "ticker_id", req.TickerId, "error", err)
		return nil, mapError(err, "GetFeatures")
	}

	result := make([]*pb.ComputedFeature, len(features))
	var nextPageToken string
	for i := range features {
		result[i] = featureToProto(&features[i])
	}
	if len(features) > 0 && int32(len(features)) == req.PageSize {
		nextPageToken = features[len(features)-1].Timestamp.Format(time.RFC3339Nano)
	}

	return &pb.GetFeaturesResponse{
		Features:      result,
		NextPageToken: nextPageToken,
	}, nil
}

func (s *MarketServer) GetExistingFeatureBarIds(ctx context.Context, req *pb.GetExistingFeatureBarIdsRequest) (*pb.GetExistingFeatureBarIdsResponse, error) {
	ids, err := s.features.GetExistingFeatureBarIds(ctx, req.TickerId, req.Timeframe, tsPtr(req.Start), tsPtr(req.End))
	if err != nil {
		s.logger.Error("GetExistingFeatureBarIds failed", "ticker_id", req.TickerId, "error", err)
		return nil, mapError(err, "GetExistingFeatureBarIds")
	}

	return &pb.GetExistingFeatureBarIdsResponse{BarIds: ids}, nil
}

func (s *MarketServer) GetExistingFeatureTimestamps(ctx context.Context, req *pb.GetExistingFeatureTimestampsRequest) (*pb.GetExistingFeatureTimestampsResponse, error) {
	timestamps, err := s.features.GetExistingFeatureTimestamps(ctx, req.TickerId, req.Timeframe, tsPtr(req.Start), tsPtr(req.End))
	if err != nil {
		s.logger.Error("GetExistingFeatureTimestamps failed", "ticker_id", req.TickerId, "error", err)
		return nil, mapError(err, "GetExistingFeatureTimestamps")
	}

	pbTimestamps := make([]*timestamppb.Timestamp, len(timestamps))
	for i, ts := range timestamps {
		pbTimestamps[i] = timestamppb.New(ts)
	}

	return &pb.GetExistingFeatureTimestampsResponse{Timestamps: pbTimestamps}, nil
}

func (s *MarketServer) BulkUpsertFeatures(ctx context.Context, req *pb.BulkUpsertFeaturesRequest) (*pb.BulkUpsertFeaturesResponse, error) {
	if len(req.Features) > 5000 {
		return nil, status.Errorf(codes.InvalidArgument, "max 5000 features per call, got %d", len(req.Features))
	}

	features := make([]repository.ComputedFeature, len(req.Features))
	for i, f := range req.Features {
		features[i] = protoToFeature(f)
	}

	count, err := s.features.BulkUpsertFeatures(ctx, features)
	if err != nil {
		s.logger.Error("BulkUpsertFeatures failed", "error", err)
		return nil, mapError(err, "BulkUpsertFeatures")
	}

	return &pb.BulkUpsertFeaturesResponse{RowsUpserted: int32(count)}, nil
}

func (s *MarketServer) StoreStates(ctx context.Context, req *pb.StoreStatesRequest) (*pb.StoreStatesResponse, error) {
	states := make([]repository.ComputedFeature, len(req.States))
	for i, st := range req.States {
		states[i] = protoToFeature(st)
	}

	count, err := s.features.StoreStates(ctx, states, req.ModelId)
	if err != nil {
		s.logger.Error("StoreStates failed", "model_id", req.ModelId, "error", err)
		return nil, mapError(err, "StoreStates")
	}

	return &pb.StoreStatesResponse{RowsStored: int32(count)}, nil
}

func (s *MarketServer) GetStates(ctx context.Context, req *pb.GetStatesRequest) (*pb.GetStatesResponse, error) {
	states, err := s.features.GetStates(ctx, req.TickerId, req.Timeframe, req.ModelId, tsPtr(req.Start), tsPtr(req.End))
	if err != nil {
		s.logger.Error("GetStates failed", "ticker_id", req.TickerId, "error", err)
		return nil, mapError(err, "GetStates")
	}

	result := make([]*pb.ComputedFeature, len(states))
	for i := range states {
		result[i] = featureToProto(&states[i])
	}

	return &pb.GetStatesResponse{States: result}, nil
}

func (s *MarketServer) GetLatestStates(ctx context.Context, req *pb.GetLatestStatesRequest) (*pb.GetLatestStatesResponse, error) {
	states, err := s.features.GetLatestStates(ctx, req.TickerId, req.Timeframe)
	if err != nil {
		s.logger.Error("GetLatestStates failed", "ticker_id", req.TickerId, "error", err)
		return nil, mapError(err, "GetLatestStates")
	}

	result := make([]*pb.ComputedFeature, len(states))
	for i := range states {
		result[i] = featureToProto(&states[i])
	}

	return &pb.GetLatestStatesResponse{States: result}, nil
}

// --- Sync Log RPCs ---

func (s *MarketServer) GetSyncLog(ctx context.Context, req *pb.GetSyncLogRequest) (*pb.GetSyncLogResponse, error) {
	sl, err := s.syncLogs.GetSyncLog(ctx, req.TickerId, req.Timeframe)
	if err != nil {
		s.logger.Error("GetSyncLog failed", "ticker_id", req.TickerId, "error", err)
		return nil, mapError(err, "GetSyncLog")
	}

	var pbSL *pb.DataSyncLog
	if sl != nil {
		pbSL = syncLogToProto(sl)
	}

	return &pb.GetSyncLogResponse{SyncLog: pbSL}, nil
}

func (s *MarketServer) UpdateSyncLog(ctx context.Context, req *pb.UpdateSyncLogRequest) (*pb.UpdateSyncLogResponse, error) {
	sl, err := s.syncLogs.UpdateSyncLog(ctx,
		req.TickerId, req.Timeframe,
		tsPtr(req.LastSyncedTimestamp), tsPtr(req.FirstSyncedTimestamp),
		req.BarsFetched, req.Status, req.ErrorMessage,
	)
	if err != nil {
		s.logger.Error("UpdateSyncLog failed", "ticker_id", req.TickerId, "error", err)
		return nil, mapError(err, "UpdateSyncLog")
	}

	return &pb.UpdateSyncLogResponse{SyncLog: syncLogToProto(sl)}, nil
}

func (s *MarketServer) ListSyncLogs(ctx context.Context, req *pb.ListSyncLogsRequest) (*pb.ListSyncLogsResponse, error) {
	var symbol *string
	if req.Symbol != nil {
		symbol = req.Symbol
	}

	logs, err := s.syncLogs.ListSyncLogs(ctx, symbol)
	if err != nil {
		s.logger.Error("ListSyncLogs failed", "error", err)
		return nil, mapError(err, "ListSyncLogs")
	}

	result := make([]*pb.DataSyncLog, len(logs))
	for i := range logs {
		result[i] = syncLogToProto(&logs[i])
	}

	return &pb.ListSyncLogsResponse{SyncLogs: result}, nil
}

// --- Conversion helpers ---

func tickerToProto(t *repository.Ticker) *pb.Ticker {
	return &pb.Ticker{
		Id:         t.ID,
		Symbol:     t.Symbol,
		Name:       t.Name,
		Exchange:   t.Exchange,
		AssetType:  t.AssetType,
		AssetClass: t.AssetClass,
		IsActive:   t.IsActive,
		CreatedAt:  timestamppb.New(t.CreatedAt),
		UpdatedAt:  timestamppb.New(t.UpdatedAt),
	}
}

func barToProto(b *repository.OHLCVBar) *pb.OHLCVBar {
	bar := &pb.OHLCVBar{
		Id:        b.ID,
		TickerId:  b.TickerID,
		Timeframe: b.Timeframe,
		Timestamp: timestamppb.New(b.Timestamp),
		Open:      b.Open,
		High:      b.High,
		Low:       b.Low,
		Close:     b.Close,
		Volume:    b.Volume,
		Source:    b.Source,
		CreatedAt: timestamppb.New(b.CreatedAt),
	}
	if b.TradeCount != nil {
		bar.TradeCount = b.TradeCount
	}
	return bar
}

func featureToProto(f *repository.ComputedFeature) *pb.ComputedFeature {
	pf := &pb.ComputedFeature{
		Id:             f.ID,
		TickerId:       f.TickerID,
		Timeframe:      f.Timeframe,
		Timestamp:      timestamppb.New(f.Timestamp),
		Features:       f.Features,
		FeatureVersion: f.FeatureVersion,
		CreatedAt:      timestamppb.New(f.CreatedAt),
	}
	if f.BarID != nil {
		pf.BarId = f.BarID
	}
	if f.ModelID != nil {
		pf.ModelId = f.ModelID
	}
	if f.StateID != nil {
		pf.StateId = f.StateID
	}
	if f.StateProb != nil {
		pf.StateProb = f.StateProb
	}
	if f.LogLikelihood != nil {
		pf.LogLikelihood = f.LogLikelihood
	}
	return pf
}

func protoToFeature(f *pb.ComputedFeature) repository.ComputedFeature {
	cf := repository.ComputedFeature{
		ID:             f.Id,
		TickerID:       f.TickerId,
		Timeframe:      f.Timeframe,
		Features:       f.Features,
		FeatureVersion: f.FeatureVersion,
	}
	if f.BarId != nil {
		cf.BarID = f.BarId
	}
	if f.Timestamp != nil {
		cf.Timestamp = f.Timestamp.AsTime()
	}
	if f.ModelId != nil {
		cf.ModelID = f.ModelId
	}
	if f.StateId != nil {
		cf.StateID = f.StateId
	}
	if f.StateProb != nil {
		cf.StateProb = f.StateProb
	}
	if f.LogLikelihood != nil {
		cf.LogLikelihood = f.LogLikelihood
	}
	return cf
}

func syncLogToProto(s *repository.DataSyncLog) *pb.DataSyncLog {
	sl := &pb.DataSyncLog{
		Id:        s.ID,
		TickerId:  s.TickerID,
		Timeframe: s.Timeframe,
		LastSyncAt: timestamppb.New(s.LastSyncAt),
		BarsFetched: s.BarsFetched,
		TotalBars:   s.TotalBars,
		Status:      s.Status,
	}
	if s.LastSyncedTimestamp != nil {
		sl.LastSyncedTimestamp = timestamppb.New(*s.LastSyncedTimestamp)
	}
	if s.FirstSyncedTimestamp != nil {
		sl.FirstSyncedTimestamp = timestamppb.New(*s.FirstSyncedTimestamp)
	}
	if s.ErrorMessage != nil {
		sl.ErrorMessage = s.ErrorMessage
	}
	return sl
}

func init() {
	// Verify interface compliance at compile time.
	var _ pb.MarketDataServiceServer = (*MarketServer)(nil)
	// Suppress unused import warning.
	_ = fmt.Sprintf
}
