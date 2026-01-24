# Algomatic State Documentation

Documentation for the Algomatic State algorithmic trading platform.

## Overview

Algomatic State provides:
- Persistent storage of OHLCV (Open, High, Low, Close, Volume) market data
- Smart incremental fetching from Alpaca API (only fetches new data)
- Support for multiple timeframes (1Min, 5Min, 15Min, 1Hour, 1Day)
- Data import from CSV/Parquet files
- REST API endpoints for data access and visualization
- React UI for regime state visualization

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

# Edit .env and set your credentials
```

Default database configuration:
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

### 6. Start the Frontend (Optional)

```bash
cd ui/frontend
npm install
npm run dev
# UI available at http://localhost:5173
```

## Using the UI

The React frontend provides an interactive visualization for regime state analysis.

### Ticker Selection
1. Select a **Ticker** from the dropdown (populated from the database)
2. Select a **Timeframe** (1Min, 5Min, 15Min, 1Hour, 1Day)
3. **Start/End dates are auto-populated** based on available data in the database

### Data Loading Behavior
- When you click **Load Data**, the system:
  1. Checks if data exists in the database for the selected range
  2. If data is missing and Alpaca API is configured, fetches from Alpaca
  3. Stores fetched data in the `ohlcv_bars` table
  4. Displays chart from database

- All chart data **always comes from the database** - never directly from Alpaca

### Visual Indicators
- **"Available: X bars"** - Shows how many bars exist in the database for the selected ticker/timeframe
- **"No data in DB"** - Indicates data will be fetched from Alpaca on load (if configured)

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

### Data Download

```bash
python scripts/download_data.py SYMBOL [OPTIONS]

Arguments:
  SYMBOL              Stock symbol to download

Options:
  --start DATE        Start date (YYYY-MM-DD)
  --end DATE          End date (YYYY-MM-DD)
  --timeframe TF      Timeframe (default: 1Min)

Example:
  python scripts/download_data.py AAPL --start 2024-01-01 --end 2024-06-01
```

## Troubleshooting

### Database Connection Failed

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

### Timezone Errors

```
TypeError: can't compare offset-naive and offset-aware datetimes
```

This error occurred in earlier versions when importing CSV/Parquet files with timezone-naive timestamps. The issue has been fixed - the loader now automatically converts naive timestamps to UTC.

If you encounter this error:
1. Update to the latest version of the codebase
2. Ensure you're using `DatabaseLoader.import_csv()` or `import_parquet()` methods

See [DATABASE.md](DATABASE.md#timezone-handling) for details on timestamp handling.

### Alpaca Sync Failures

```
Alpaca credentials not configured
```

Set Alpaca credentials in `.env`:
```bash
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_secret_key
```

## Documentation Index

- [DATABASE.md](DATABASE.md) - Database schema, migrations, and configuration
- [APIs.md](APIs.md) - REST API reference
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture details
- [FEATURE.md](FEATURE.md) - Feature engineering documentation
