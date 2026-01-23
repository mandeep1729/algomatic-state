# PostgreSQL Database Integration

This document covers the PostgreSQL database setup for storing and managing OHLCV market data in Algomatic State.

## Overview

The database integration provides:
- Persistent storage of OHLCV (Open, High, Low, Close, Volume) market data
- Smart incremental fetching from Alpaca API (only fetches new data)
- Support for multiple timeframes (1Min, 5Min, 15Min, 1Hour, 1Day)
- Data import from CSV/Parquet files
- REST API endpoints for data access and synchronization

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   React UI      │────▶│   FastAPI       │────▶│   PostgreSQL    │
│   (Frontend)    │     │   (Backend)     │     │   (Database)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │   Alpaca API    │
                        │   (Data Source) │
                        └─────────────────┘
```

## Quick Start

### 1. Start PostgreSQL

```bash
# Start PostgreSQL container
docker-compose up -d postgres

# (Optional) Start pgAdmin for database management
docker-compose --profile tools up -d
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and set your credentials (especially ALPACA keys if using)
```

Default database configuration in `.env`:
```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=algomatic
DB_USER=algomatic
DB_PASSWORD=algomatic_dev
```

### 3. Initialize Database

```bash
# Activate virtual environment
source .venv/bin/activate

# Initialize database and seed with common tickers
python scripts/init_db.py --seed
```

### 4. Import Existing Data (Optional)

```bash
# Import a single file
python scripts/import_csv_to_db.py AAPL --file data/raw/AAPL_1Min.parquet

# Import all parquet files from a directory
python scripts/import_csv_to_db.py --all --dir data/raw
```

### 5. Start the API Server

```bash
python ui/run_backend.py
# API available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

## Database Schema

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
| source | VARCHAR(20) | 'alpaca', 'csv_import' |
| created_at | TIMESTAMPTZ | Record creation time |

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

## API Endpoints

### Data Sources

#### `GET /api/sources`
List all available data sources (database tickers, local files, Alpaca).

#### `GET /api/tickers`
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

### OHLCV Data

#### `GET /api/ohlcv/{symbol}`
Load OHLCV data for a symbol.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| source_type | string | "database" | "database", "local", or "alpaca" |
| timeframe | string | "1Min" | Bar timeframe |
| start_date | string | -30 days | Start date (YYYY-MM-DD) |
| end_date | string | now | End date (YYYY-MM-DD) |

**Example:**
```bash
curl "http://localhost:8000/api/ohlcv/AAPL?timeframe=1Min&start_date=2024-01-01"
```

### Data Synchronization

#### `GET /api/tickers/{symbol}/summary`
Get data summary for a ticker (available timeframes and date ranges).

#### `GET /api/sync-status/{symbol}`
Get synchronization status for a symbol.

#### `POST /api/sync/{symbol}`
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

### Data Import

#### `POST /api/import`
Import data from a local file.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| symbol | string | Symbol to import as |
| file_path | string | Path to CSV/Parquet file |
| timeframe | string | Timeframe of the data |

### Health Check

#### `GET /api/health`
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

## Command Line Tools

### Database Initialization

```bash
python scripts/init_db.py [OPTIONS]

Options:
  --seed              Seed database with common tickers (SPY, AAPL, etc.)
  --skip-migrations   Skip Alembic migrations, use direct table creation
```

### Data Import

```bash
python scripts/import_csv_to_db.py [SYMBOL] [OPTIONS]

Arguments:
  SYMBOL              Stock symbol (optional if using --all)

Options:
  --file PATH         Path to CSV or Parquet file
  --timeframe TF      Timeframe (default: 1Min)
  --all               Import all files in directory
  --dir PATH          Directory to scan (default: data/raw)
  --pattern GLOB      File pattern (default: *.parquet)

Examples:
  # Import single file
  python scripts/import_csv_to_db.py AAPL --file data/raw/AAPL_1Min.parquet

  # Import all parquet files
  python scripts/import_csv_to_db.py --all --dir data/raw

  # Import with specific pattern
  python scripts/import_csv_to_db.py --all --pattern "SPY*.csv"
```

## Docker Compose Services

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

## Database Migrations

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

### Python Configuration

```python
from config.settings import get_settings

settings = get_settings()
print(settings.database.url)
# postgresql://algomatic:password@localhost:5432/algomatic
```

## Troubleshooting

### Connection Failed

```
Database connection failed!
```

1. Ensure PostgreSQL is running:
   ```bash
   docker-compose up -d postgres
   docker ps  # Verify container is running
   ```

2. Check credentials in `.env` file

3. Verify network connectivity:
   ```bash
   docker exec algomatic-postgres psql -U algomatic -d algomatic -c "SELECT 1"
   ```

### Migration Errors

```
alembic.util.exc.CommandError: Can't locate revision
```

Reset migrations:
```bash
# Drop all tables (WARNING: deletes data)
docker exec algomatic-postgres psql -U algomatic -d algomatic -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Re-run migrations
alembic upgrade head
```

### Import Errors

```
Error: File not found
```

Ensure file path is correct and file exists:
```bash
ls -la data/raw/AAPL_1Min.parquet
```

### Alpaca Sync Failures

```
Alpaca credentials not configured
```

Set Alpaca credentials in `.env`:
```bash
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_secret_key
```

## Performance Considerations

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
