# Database Schema & Configuration

PostgreSQL database schema and configuration for storing OHLCV market data.

## Schema

### Tables

#### `tickers`
Stores symbol metadata.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| symbol | VARCHAR(20) | Stock symbol (e.g., 'AAPL') |
| name | VARCHAR(255) | Company name |
| exchange | VARCHAR(50) | Exchange (NYSE, NASDAQ, etc.) |
| asset_type | VARCHAR(20) | 'stock', 'etf', etc. |
| is_active | BOOLEAN | Whether ticker is active |
| created_at | TIMESTAMPTZ | Record creation time |
| updated_at | TIMESTAMPTZ | Last update time |

#### `ohlcv_bars`
Stores price and volume data.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| ticker_id | INTEGER | Foreign key to tickers |
| timeframe | VARCHAR(10) | '1Min', '5Min', '15Min', '1Hour', '1Day' |
| timestamp | TIMESTAMPTZ | Bar timestamp (UTC) |
| open | FLOAT | Opening price |
| high | FLOAT | High price |
| low | FLOAT | Low price |
| close | FLOAT | Closing price |
| volume | BIGINT | Trading volume |
| trade_count | INTEGER | Number of trades (optional) |
| source | VARCHAR(20) | 'alpaca', 'csv_import' |
| created_at | TIMESTAMPTZ | Record creation time |

#### `computed_features`
Stores derived technical indicators and features. Using JSONB for flexibility.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| bar_id | BIGINT | Foreign key to ohlcv_bars |
| ticker_id | INTEGER | Foreign key to tickers (denormalized for query speed) |
| timeframe | VARCHAR(10) | Timeframe |
| timestamp | TIMESTAMPTZ | Timestamp |
| features | JSONB | Dictionary of feature values |
| feature_version | VARCHAR(20) | Version string for feature set |
| created_at | TIMESTAMPTZ | Creation time |

#### `data_sync_log`
Tracks data synchronization status.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| ticker_id | INTEGER | Foreign key to tickers |
| timeframe | VARCHAR(10) | Timeframe being synced |
| last_synced_timestamp | TIMESTAMPTZ | Most recent data point |
| first_synced_timestamp | TIMESTAMPTZ | Earliest data point |
| last_sync_at | TIMESTAMPTZ | When sync was performed |
| bars_fetched | INTEGER | Bars fetched in last sync |
| total_bars | INTEGER | Total bars in database |
| status | VARCHAR(20) | 'success', 'partial', 'failed' |
| error_message | TEXT | Error details if failed |

## Migrations

Alembic is used for database migrations.

```bash
# Run pending migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "Description"

# Downgrade one revision
alembic downgrade -1

# View migration history
alembic history
```

## Docker Services

### PostgreSQL

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: algomatic-postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

### pgAdmin (Optional)

```bash
# Start pgAdmin for database management UI
docker-compose --profile tools up -d

# Access at http://localhost:5050
# Default login: admin@algomatic.local / admin
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DB_HOST | localhost | Database host |
| DB_PORT | 5432 | Database port |
| DB_NAME | algomatic | Database name |
| DB_USER | algomatic | Database user |
| DB_PASSWORD | | Database password |
| DB_POOL_SIZE | 5 | Connection pool size |
| DB_MAX_OVERFLOW | 10 | Max overflow connections |
| DB_ECHO | false | Log SQL statements |

### Python Usage

```python
from config.settings import get_settings

settings = get_settings()
print(settings.database.url)
# postgresql://algomatic:password@localhost:5432/algomatic
```

## Smart Data Fetching

The `DatabaseLoader` implements intelligent incremental fetching:

1. **Check existing data**: Query database for the latest timestamp
2. **Determine gaps**: Compare requested range with existing data
3. **Fetch only new data**: Request Alpaca API for missing periods only
4. **Store and return**: Insert new bars and return complete dataset

```
Request: AAPL 1Min data for Jan 1-15
           │
           ▼
    ┌──────────────┐
    │ DB has data  │
    │ Jan 1-10     │
    └──────────────┘
           │
           ▼
    ┌──────────────┐
    │ Fetch Alpaca │
    │ Jan 11-15    │  ◀── Only fetches missing data
    └──────────────┘
           │
           ▼
    ┌──────────────┐
    │ Return full  │
    │ Jan 1-15     │
    └──────────────┘
```

## Performance

### Indexes

The following indexes are created for query performance:

- `ix_tickers_symbol` - Fast symbol lookup
- `ix_ohlcv_ticker_timeframe_ts` - Primary query pattern
- `ix_ohlcv_timestamp` - Time-based queries

### Connection Pooling

Default pool settings:
- Pool size: 5 connections
- Max overflow: 10 additional connections
- Pre-ping enabled for connection health checks

### Bulk Inserts

Data imports use PostgreSQL's `INSERT ... ON CONFLICT DO NOTHING` for efficient upserts without duplicates.

## Data Integrity

### Constraints

- Unique constraint on (ticker_id, timeframe, timestamp)
- Check constraints for OHLCV data validity:
  - `high >= low`
  - `high >= open AND high >= close`
  - `low <= open AND low <= close`
  - All prices > 0
  - Volume >= 0

### Cascading Deletes

Deleting a ticker automatically removes:
- All associated OHLCV bars
- All sync log entries
