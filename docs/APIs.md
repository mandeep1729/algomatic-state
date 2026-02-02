# REST API Reference

FastAPI backend endpoints for market data access and visualization.

**Base URL:** `http://localhost:8000`
**Swagger Docs:** `http://localhost:8000/docs`

## Tickers

### `GET /api/tickers`
List all tickers stored in the database.

**Response:**
```json
[
  {
    "symbol": "AAPL",
    "name": "Apple Inc.",
    "exchange": "NASDAQ",
    "is_active": true,
    "timeframes": ["1Min", "1Day"]
  }
]
```

### `GET /api/tickers/{symbol}/summary`
Get data summary for a ticker (available timeframes and date ranges).

**Response:**
```json
{
  "symbol": "AAPL",
  "timeframes": {
    "1Min": {
      "earliest": "2024-01-01T09:30:00",
      "latest": "2024-01-15T16:00:00",
      "bar_count": 5850
    }
  }
}
```

## OHLCV Data

### `GET /api/ohlcv/{symbol}`
Load OHLCV data for a symbol from the database.

Data is always loaded from the PostgreSQL database. If data is not available for the requested range and Alpaca API is configured, it will be automatically fetched from Alpaca and stored in the database before returning.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| timeframe | string | "1Min" | Bar timeframe (1Min, 5Min, 15Min, 1Hour, 1Day) |
| start_date | string | -30 days | Start date (YYYY-MM-DD) |
| end_date | string | now | End date (YYYY-MM-DD) |

**Example:**
```bash
curl "http://localhost:8000/api/ohlcv/AAPL?timeframe=1Min&start_date=2024-01-01"
```

**Response:**
```json
{
  "timestamps": ["2024-01-01 09:30:00", "2024-01-01 09:31:00"],
  "open": [150.25, 150.45],
  "high": [150.50, 150.75],
  "low": [150.10, 150.40],
  "close": [150.45, 150.60],
  "volume": [2500000, 1800000]
}
```

**Data Flow:**
1. Check if data exists in database for the requested range
2. If missing and Alpaca configured → Fetch from Alpaca → Store in `ohlcv_bars` table
3. Return data from database

## Features & Regimes

### `GET /api/features/{symbol}`
Compute and return technical features for the data.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| timeframe | string | "1Min" | Bar timeframe |
| start_date | string | null | Start date (YYYY-MM-DD) |
| end_date | string | null | End date (YYYY-MM-DD) |

**Response:**
```json
{
  "timestamps": ["2024-01-01 09:30:00"],
  "features": {
    "r1": [0.001],
    "r5": [0.005],
    "rv_15": [0.02]
  },
  "feature_names": ["r1", "r5", "rv_15"]
}
```

### `GET /api/regimes/{symbol}`
Compute and return regime states (clustering analysis).

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| timeframe | string | "1Min" | Bar timeframe |
| start_date | string | null | Start date |
| end_date | string | null | End date |
| n_clusters | int | 5 | Number of regimes (2-10) |
| window_size | int | 60 | Window size (10-200) |
| n_components | int | 8 | PCA components (2-20) |

**Response:**
```json
{
  "timestamps": ["2024-01-01 09:30:00"],
  "regime_labels": [0, 1, 2, 0],
  "regime_info": [
    {"label": 0, "size": 100, "mean_return": 0.001, "sharpe": 1.5}
  ],
  "transition_matrix": [[0.8, 0.1, 0.1], [0.2, 0.7, 0.1], [0.1, 0.2, 0.7]],
  "explained_variance": 0.85,
  "n_samples": 1000
}
```

### `GET /api/statistics/{symbol}`
Get comprehensive statistics summary.

**Response:**
```json
{
  "ohlcv_stats": {
    "total_bars": 5000,
    "date_range": {"start": "2024-01-01", "end": "2024-01-15"},
    "price": {"min": 145.0, "max": 155.0, "mean": 150.0},
    "volume": {"min": 100000, "max": 5000000, "mean": 1500000},
    "returns": {"total_return": 3.5, "daily_volatility": 1.2}
  },
  "feature_stats": {
    "r1": {"min": -0.05, "max": 0.05, "mean": 0.0001}
  },
  "regime_stats": {
    "n_regimes": 5,
    "explained_variance": 0.85
  }
}
```

## State Analysis

### `POST /api/analyze/{symbol}`
Analyze a symbol using HMM: load OHLCV data, compute features, train model if needed, compute states.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| timeframe | string | "1Min" | Timeframe to analyze |

**Example:**
```bash
curl -X POST "http://localhost:8000/api/analyze/AAPL?timeframe=1Hour"
```

**Response:**
```json
{
  "symbol": "AAPL",
  "timeframe": "1Hour",
  "features_computed": 0,
  "model_trained": true,
  "model_id": "state_v001",
  "states_computed": 803,
  "total_bars": 803,
  "message": "OHLCV data loaded; Trained new model state_v001 with 11 states; Computed 803 states"
}
```

### `POST /api/pca/analyze/{symbol}`
Analyze a symbol using PCA + K-means clustering (simpler alternative to HMM).

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| timeframe | string | "1Min" | Timeframe to analyze |
| n_components | int | auto | Number of PCA components (auto = 95% variance) |
| n_states | int | auto | Number of K-means clusters (auto = elbow method) |

**Example:**
```bash
curl -X POST "http://localhost:8000/api/pca/analyze/AAPL?timeframe=1Hour"
```

**Response:**
```json
{
  "symbol": "AAPL",
  "timeframe": "1Hour",
  "features_computed": 0,
  "model_trained": true,
  "model_id": "pca_v001",
  "states_computed": 803,
  "n_components": 8,
  "n_states": 4,
  "total_variance_explained": 0.975,
  "message": "OHLCV data loaded; Trained PCA model: 8 components, 4 states, 97.5% variance explained; Computed 803 states"
}
```

### `GET /api/pca/regimes/{symbol}`
Get PCA-based regime states for a symbol.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| timeframe | string | "1Min" | Timeframe |
| model_id | string | latest | Model ID to use |
| start_date | string | null | Start date (YYYY-MM-DD) |
| end_date | string | null | End date (YYYY-MM-DD) |

**Response:**
```json
{
  "timestamps": ["2024-01-01 09:30:00", "2024-01-01 10:30:00"],
  "state_ids": [0, 1],
  "state_info": {
    "0": {
      "label": "up_trending",
      "short_label": "UT-TRE",
      "color": "#22c55e",
      "description": "Upward movement with strong trend"
    },
    "1": {
      "label": "down_trending",
      "short_label": "DT-TRE",
      "color": "#ef4444",
      "description": "Downward movement with strong trend"
    }
  }
}
```

**State Labels:**
- `up_trending` / `up_volatile` / `up_breakout` - Bullish states (green)
- `down_trending` / `down_volatile` / `down_breakout` - Bearish states (red)
- `neutral_consolidation` / `neutral_ranging` - Sideways states (gray)

## Data Synchronization

### `GET /api/sync-status/{symbol}`
Get synchronization status for a symbol.

**Response:**
```json
[
  {
    "symbol": "AAPL",
    "timeframe": "1Min",
    "last_synced_timestamp": "2024-01-15T16:00:00",
    "first_synced_timestamp": "2024-01-01T09:30:00",
    "last_sync_at": "2024-01-15T18:00:00",
    "bars_fetched": 500,
    "total_bars": 5850,
    "status": "success",
    "error_message": null
  }
]
```

### `POST /api/sync/{symbol}`
Trigger data synchronization from Alpaca.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| timeframe | string | "1Min" | Timeframe to sync |
| start_date | string | -30 days | Start date |
| end_date | string | now | End date |

**Example:**
```bash
curl -X POST "http://localhost:8000/api/sync/AAPL?timeframe=1Min&start_date=2024-01-01"
```

**Response:**
```json
{
  "message": "Sync completed for AAPL/1Min",
  "bars_loaded": 5850,
  "date_range": {
    "start": "2024-01-01T09:30:00",
    "end": "2024-01-15T16:00:00"
  }
}
```

## Data Import

### `POST /api/import`
Import data from a local file into the database.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| symbol | string | Symbol to import as |
| file_path | string | Path to CSV/Parquet file |
| timeframe | string | Timeframe of the data |

**Example:**
```bash
curl -X POST "http://localhost:8000/api/import?symbol=AAPL&file_path=/data/raw/AAPL_1Min.parquet&timeframe=1Min"
```

**Response:**
```json
{
  "message": "Import completed for AAPL/1Min",
  "rows_imported": 5850
}
```

## System

### `GET /api/health`
Check system health including database connectivity.

**Response:**
```json
{
  "status": "healthy",
  "api": true,
  "database": true,
  "alpaca": true
}
```

### `DELETE /api/cache`
Clear the in-memory data cache.

**Response:**
```json
{
  "message": "Cache cleared"
}
```

## Error Responses

All endpoints return standard HTTP error codes:

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Invalid Alpaca credentials |
| 404 | Not Found - Symbol or file not found |
| 500 | Internal Server Error |

**Error Response Format:**
```json
{
  "detail": "Error message describing what went wrong"
}
```

## Broker Integration

### `POST /api/trading-buddy/connect`
Initiate a broker connection using SnapTrade.

**Response:**
```json
{
  "redirect_url": "https://app.snaptrade.com/..."
}
```

### `POST /api/trading-buddy/sync`
Sync trade history from connected brokers.

**Response:**
```json
{
  "status": "success",
  "trades_synced": 50
}
```

### `GET /api/trading-buddy/trades`
Get trade history.

**Response:**
```json
[
  {
    "symbol": "AAPL",
    "side": "BUY",
    "quantity": 10,
    "price": 150.0,
    "executed_at": "2024-01-01T10:00:00",
    "brokerage": "Robinhood"
  }
]
```
