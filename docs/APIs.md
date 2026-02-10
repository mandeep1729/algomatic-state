# REST API Reference

FastAPI backend endpoints for market data access and visualization.

**Base URL:** `http://localhost:8729` (configurable via `SERVER_PORT` in `.env`)
**Swagger Docs:** `http://localhost:8729/docs`

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
curl "http://localhost:8729/api/ohlcv/AAPL?timeframe=1Min&start_date=2024-01-01"
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
curl -X POST "http://localhost:8729/api/analyze/AAPL?timeframe=1Hour"
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
curl -X POST "http://localhost:8729/api/pca/analyze/AAPL?timeframe=1Hour"
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
curl -X POST "http://localhost:8729/api/sync/AAPL?timeframe=1Min&start_date=2024-01-01"
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
curl -X POST "http://localhost:8729/api/import?symbol=AAPL&file_path=/data/raw/AAPL_1Min.parquet&timeframe=1Min"
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

## Feature Computation

### `POST /api/compute-features/{symbol}`
Compute technical features for all timeframes of a ticker.

Computes the full feature set including returns, volatility, volume, intrabar, anchor, time-of-day, and TA-Lib indicators.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| force | boolean | false | Recompute features for all bars |

**Example:**
```bash
curl -X POST "http://localhost:8729/api/compute-features/AAPL"
```

**Response:**
```json
{
  "symbol": "AAPL",
  "timeframes_processed": 3,
  "timeframes_skipped": 2,
  "features_stored": 1500,
  "message": "Computed features for AAPL: 1500 rows stored"
}
```

## Trading Buddy

### `POST /api/trading-buddy/evaluate`
Evaluate a proposed trade intent.

**Request Body:**
```json
{
  "symbol": "AAPL",
  "direction": "long",
  "timeframe": "15Min",
  "entry_price": 150.00,
  "stop_loss": 148.00,
  "profit_target": 155.00,
  "position_size": 100,
  "rationale": "Breakout above resistance"
}
```

**Response:**
```json
{
  "score": 75,
  "summary": "Trade has moderate risk. Watch for regime conflict.",
  "items": [
    {
      "evaluator": "risk_reward",
      "code": "RR_RATIO",
      "severity": "info",
      "title": "Risk/Reward Ratio",
      "message": "R:R of 2.5:1 meets minimum threshold",
      "evidence": [{"label": "R:R", "value": "2.5:1"}]
    },
    {
      "evaluator": "regime_fit",
      "code": "REGIME_CONFLICT",
      "severity": "warning",
      "title": "Regime Conflict",
      "message": "Current regime is bearish, trade is long",
      "evidence": [{"label": "Regime", "value": "down_trending"}]
    }
  ],
  "blocker_count": 0,
  "critical_count": 0,
  "warning_count": 1,
  "info_count": 1
}
```

## Broker Integration

### `POST /api/broker/connect`
Initiate a broker connection using SnapTrade.

**Response:**
```json
{
  "redirect_url": "https://app.snaptrade.com/..."
}
```

### `POST /api/broker/sync`
Sync trade history from connected brokers.

**Response:**
```json
{
  "status": "success",
  "trades_synced": 50
}
```

### `GET /api/broker/trades`
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

## Position Campaigns

### `GET /api/campaigns`
Get all position campaigns for the authenticated user.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| status | string | null | Filter by 'open' or 'closed' |
| symbol | string | null | Filter by symbol |
| limit | int | 50 | Max campaigns to return |

**Response:**
```json
[
  {
    "id": 1,
    "symbol": "AAPL",
    "direction": "long",
    "status": "closed",
    "opened_at": "2024-01-01T10:00:00",
    "closed_at": "2024-01-02T14:30:00",
    "qty_opened": 100,
    "qty_closed": 100,
    "avg_open_price": 150.00,
    "avg_close_price": 155.00,
    "realized_pnl": 500.00,
    "return_pct": 3.33,
    "num_fills": 2
  }
]
```

### `GET /api/campaigns/{id}`
Get a specific campaign with its legs.

**Response:**
```json
{
  "id": 1,
  "symbol": "AAPL",
  "direction": "long",
  "status": "closed",
  "realized_pnl": 500.00,
  "legs": [
    {
      "id": 1,
      "leg_type": "open",
      "side": "buy",
      "quantity": 100,
      "avg_price": 150.00,
      "started_at": "2024-01-01T10:00:00"
    },
    {
      "id": 2,
      "leg_type": "close",
      "side": "sell",
      "quantity": 100,
      "avg_price": 155.00,
      "started_at": "2024-01-02T14:30:00"
    }
  ]
}
```

### `GET /api/campaigns/stats`
Get aggregate statistics for campaigns.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| period | string | 'all' | 'day', 'week', 'month', 'year', 'all' |

**Response:**
```json
{
  "total_campaigns": 50,
  "winning_campaigns": 30,
  "losing_campaigns": 20,
  "win_rate": 0.60,
  "total_pnl": 5000.00,
  "avg_pnl": 100.00,
  "avg_win": 250.00,
  "avg_loss": -125.00,
  "profit_factor": 2.0
}
```

## Authentication

### `POST /api/auth/google`
Authenticate with Google OAuth. Verifies the Google ID token, finds or creates the user account, and returns a JWT.

**Request Body:**
```json
{
  "credential": "<Google ID token from frontend>"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "name": "John Doe",
    "email": "john@example.com",
    "profile_picture_url": "https://...",
    "auth_provider": "google"
  }
}
```

### `GET /api/auth/me`
Get the current authenticated user's information. Requires Bearer token.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "id": 1,
  "name": "John Doe",
  "email": "john@example.com",
  "profile_picture_url": "https://...",
  "google_id": "...",
  "auth_provider": "google",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00"
}
```

### `POST /api/auth/logout`
Logout endpoint. Since JWT is stateless, the client should discard the token.

**Response:**
```json
{
  "message": "Logged out successfully"
}
```

## User Profile

### `GET /api/user/profile`
Get the authenticated user's trading profile. Requires Bearer token.

**Response:**
```json
{
  "account_balance": 100000.0,
  "max_position_size_pct": 10.0,
  "max_risk_per_trade_pct": 2.0,
  "max_daily_loss_pct": 5.0,
  "min_risk_reward_ratio": 2.0,
  "default_timeframes": ["1Min", "15Min", "1Hour"],
  "experience_level": "intermediate",
  "trading_style": "swing"
}
```

### `PUT /api/user/profile`
Update the authenticated user's trading profile.

**Request Body:**
```json
{
  "account_balance": 150000.0,
  "max_position_size_pct": 5.0,
  "experience_level": "advanced"
}
```

**Response:** Same as `GET /api/user/profile`

### `GET /api/user/risk`
Get the authenticated user's risk preferences (subset of profile).

**Response:**
```json
{
  "max_position_size_pct": 10.0,
  "max_risk_per_trade_pct": 2.0,
  "max_daily_loss_pct": 5.0,
  "min_risk_reward_ratio": 2.0
}
```

### `PUT /api/user/risk`
Update the authenticated user's risk preferences.

**Request Body:**
```json
{
  "max_risk_per_trade_pct": 1.5,
  "min_risk_reward_ratio": 3.0
}
```

**Response:** Same as `GET /api/user/risk`
