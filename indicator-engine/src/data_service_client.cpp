#include "data_service_client.h"

#include <grpcpp/grpcpp.h>
#include <spdlog/spdlog.h>

#include "market/v1/service.grpc.pb.h"
#include "market/v1/bar.pb.h"
#include "market/v1/ticker.pb.h"
#include "market/v1/feature.pb.h"

#include <google/protobuf/timestamp.pb.h>

namespace ie {

namespace {

google::protobuf::Timestamp* make_timestamp(time_t epoch) {
    auto* ts = new google::protobuf::Timestamp();
    ts->set_seconds(epoch);
    ts->set_nanos(0);
    return ts;
}

void check_status(const grpc::Status& status, const std::string& method) {
    if (!status.ok()) {
        throw std::runtime_error(
            method + " failed: [" + std::to_string(status.error_code()) + "] " + status.error_message());
    }
}

} // anonymous namespace

struct DataServiceClient::Impl {
    std::shared_ptr<grpc::Channel> channel;
    std::unique_ptr<market::v1::MarketDataService::Stub> stub;

    explicit Impl(const std::string& target) {
        channel = grpc::CreateChannel(target, grpc::InsecureChannelCredentials());
        stub = market::v1::MarketDataService::NewStub(channel);
        spdlog::info("DataServiceClient connected to {}", target);
    }
};

DataServiceClient::DataServiceClient(const std::string& target)
    : impl_(std::make_unique<Impl>(target)) {}

DataServiceClient::~DataServiceClient() = default;

std::vector<OHLCVBar> DataServiceClient::read_ohlcv_bars(
    int64_t ticker_id,
    const std::string& timeframe,
    time_t start,
    time_t end) const
{
    market::v1::StreamBarsRequest req;
    req.set_ticker_id(static_cast<int32_t>(ticker_id));
    req.set_timeframe(timeframe);

    if (start > 0) {
        req.set_allocated_start(make_timestamp(start));
    }
    if (end > 0) {
        req.set_allocated_end(make_timestamp(end));
    }

    grpc::ClientContext ctx;
    auto reader = impl_->stub->StreamBars(&ctx, req);

    std::vector<OHLCVBar> bars;
    market::v1::OHLCVBar pb_bar;

    while (reader->Read(&pb_bar)) {
        OHLCVBar bar;
        bar.id = pb_bar.id();
        bar.ticker_id = pb_bar.ticker_id();
        bar.timestamp = pb_bar.timestamp().seconds();
        bar.open = pb_bar.open();
        bar.high = pb_bar.high();
        bar.low = pb_bar.low();
        bar.close = pb_bar.close();
        bar.volume = pb_bar.volume();
        bars.push_back(bar);
    }

    auto status = reader->Finish();
    check_status(status, "StreamBars");

    spdlog::debug("Read {} OHLCV bars via gRPC for ticker_id={} timeframe={}", bars.size(), ticker_id, timeframe);
    return bars;
}

std::set<int64_t> DataServiceClient::get_existing_feature_bar_ids(
    int64_t ticker_id,
    const std::string& timeframe,
    time_t start,
    time_t end) const
{
    market::v1::GetExistingFeatureBarIdsRequest req;
    req.set_ticker_id(static_cast<int32_t>(ticker_id));
    req.set_timeframe(timeframe);

    if (start > 0) {
        req.set_allocated_start(make_timestamp(start));
    }
    if (end > 0) {
        req.set_allocated_end(make_timestamp(end));
    }

    grpc::ClientContext ctx;
    market::v1::GetExistingFeatureBarIdsResponse resp;
    auto status = impl_->stub->GetExistingFeatureBarIds(&ctx, req, &resp);
    check_status(status, "GetExistingFeatureBarIds");

    std::set<int64_t> ids(resp.bar_ids().begin(), resp.bar_ids().end());
    return ids;
}

std::vector<Ticker> DataServiceClient::get_active_tickers() const {
    market::v1::ListTickersRequest req;
    req.set_active_only(true);

    grpc::ClientContext ctx;
    market::v1::ListTickersResponse resp;
    auto status = impl_->stub->ListTickers(&ctx, req, &resp);
    check_status(status, "ListTickers");

    std::vector<Ticker> tickers;
    tickers.reserve(resp.tickers_size());
    for (const auto& t : resp.tickers()) {
        tickers.push_back({t.id(), t.symbol()});
    }
    return tickers;
}

Ticker DataServiceClient::get_ticker(const std::string& symbol) const {
    market::v1::GetTickerRequest req;
    req.set_symbol(symbol);

    grpc::ClientContext ctx;
    market::v1::GetTickerResponse resp;
    auto status = impl_->stub->GetTicker(&ctx, req, &resp);

    if (status.error_code() == grpc::StatusCode::NOT_FOUND) {
        return {0, ""};
    }
    check_status(status, "GetTicker");

    return {resp.ticker().id(), resp.ticker().symbol()};
}

int DataServiceClient::batch_upsert_features(
    const std::vector<IndicatorResult>& results,
    int64_t ticker_id,
    const std::string& timeframe,
    const std::string& feature_version) const
{
    if (results.empty()) return 0;

    constexpr size_t CHUNK_SIZE = 5000;
    int total_upserted = 0;

    for (size_t i = 0; i < results.size(); i += CHUNK_SIZE) {
        size_t chunk_end = std::min(i + CHUNK_SIZE, results.size());

        market::v1::BulkUpsertFeaturesRequest req;

        for (size_t j = i; j < chunk_end; j++) {
            const auto& r = results[j];
            auto* f = req.add_features();
            f->set_bar_id(r.bar_id);
            f->set_ticker_id(static_cast<int32_t>(ticker_id));
            f->set_timeframe(timeframe);
            f->set_feature_version(feature_version);

            // Set features map, filtering NaN/Inf.
            auto* feat_map = f->mutable_features();
            for (const auto& [key, val] : r.features) {
                if (std::isfinite(val)) {
                    (*feat_map)[key] = val;
                }
            }
        }

        grpc::ClientContext ctx;
        market::v1::BulkUpsertFeaturesResponse resp;
        auto status = impl_->stub->BulkUpsertFeatures(&ctx, req, &resp);
        check_status(status, "BulkUpsertFeatures");

        total_upserted += resp.rows_upserted();
        spdlog::debug("Upserted feature batch {}-{} ({} rows) for ticker_id={} timeframe={}",
                       i, chunk_end, resp.rows_upserted(), ticker_id, timeframe);
    }

    return total_upserted;
}

bool DataServiceClient::health_check() const {
    // Simple health check: try to list tickers.
    try {
        market::v1::ListTickersRequest req;
        req.set_active_only(true);

        grpc::ClientContext ctx;
        // Set a short deadline.
        ctx.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(5));

        market::v1::ListTickersResponse resp;
        auto status = impl_->stub->ListTickers(&ctx, req, &resp);
        return status.ok();
    } catch (...) {
        return false;
    }
}

} // namespace ie
