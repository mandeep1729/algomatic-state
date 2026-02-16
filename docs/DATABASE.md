# Database Schema & Configuration

PostgreSQL database schema and configuration for the Trading Buddy platform.

## Schema Overview

The database consists of four main domains:

1. **Market Data** - OHLCV bars, features, sync tracking
2. **User Management** - Accounts, profiles, custom rules
3. **Trade Evaluation** - Intents, evaluations, strategies
4. **Trade Lifecycle** - Campaigns, legs, lots, closures

## Market Data Tables

### `tickers`
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

### `ohlcv_bars`
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
| source | VARCHAR(20) | 'alpaca', 'finnhub', 'csv_import', 'aggregated' |
| created_at | TIMESTAMPTZ | Record creation time |

### `computed_features`
Stores derived technical indicators, features, and HMM state assignments.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| bar_id | BIGINT | Foreign key to ohlcv_bars (unique) |
| ticker_id | INTEGER | Foreign key to tickers (denormalized) |
| timeframe | VARCHAR(10) | Timeframe |
| timestamp | TIMESTAMPTZ | Timestamp |
| features | JSONB | Dictionary of feature values |
| feature_version | VARCHAR(20) | Version string for feature set |
| model_id | VARCHAR(50) | HMM model identifier |
| state_id | INTEGER | Assigned regime state (-1 for OOD) |
| state_prob | FLOAT | State probability (0-1) |
| log_likelihood | FLOAT | Log likelihood of observation |
| created_at | TIMESTAMPTZ | Creation time |

### `data_sync_log`
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

## User Management Tables

### `user_accounts`
User account with authentication and personal details.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| external_user_id | VARCHAR(100) | External identifier (unique) |
| name | VARCHAR(255) | User's name |
| email | VARCHAR(255) | Email address (unique) |
| google_id | VARCHAR(255) | Google OAuth ID (unique) |
| auth_provider | VARCHAR(50) | 'google' |
| profile_picture_url | VARCHAR(1024) | Profile image URL |
| is_active | BOOLEAN | Account status |
| created_at | TIMESTAMPTZ | Creation time |
| updated_at | TIMESTAMPTZ | Last update time |

### `user_profiles`
Trading and risk preferences (one-to-one with user_accounts).

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| user_account_id | INTEGER | Foreign key to user_accounts (unique) |
| account_balance | FLOAT | Trading account balance |
| max_position_size_pct | FLOAT | Max position size (% of account) |
| max_risk_per_trade_pct | FLOAT | Max risk per trade (%) |
| max_daily_loss_pct | FLOAT | Max daily loss limit (%) |
| min_risk_reward_ratio | FLOAT | Minimum R:R ratio |
| default_timeframes | JSONB | Preferred timeframes for analysis |
| experience_level | VARCHAR(50) | 'beginner', 'intermediate', 'advanced' |
| trading_style | VARCHAR(50) | 'scalp', 'day', 'swing', 'position' |
| created_at | TIMESTAMPTZ | Creation time |
| updated_at | TIMESTAMPTZ | Last update time |

### `user_rules`
Custom evaluation rules per user.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| account_id | INTEGER | Foreign key to user_accounts |
| rule_code | VARCHAR(50) | Rule identifier |
| evaluator | VARCHAR(100) | Evaluator that uses this rule |
| parameters | JSONB | Rule parameters (thresholds, severity) |
| is_enabled | BOOLEAN | Whether rule is active |
| description | TEXT | Rule description |
| created_at | TIMESTAMPTZ | Creation time |
| updated_at | TIMESTAMPTZ | Last update time |

### `strategies`
User-defined trading strategies.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| account_id | INTEGER | Foreign key to user_accounts |
| name | VARCHAR(100) | Strategy name (unique per account) |
| description | TEXT | Strategy description |
| is_active | BOOLEAN | Whether strategy is active |
| created_at | TIMESTAMPTZ | Creation time |
| updated_at | TIMESTAMPTZ | Last update time |

## Trade Evaluation Tables

### `trade_intents`
User's proposed trade for evaluation.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| account_id | INTEGER | Foreign key to user_accounts |
| symbol | VARCHAR(20) | Stock symbol |
| direction | VARCHAR(10) | 'long' or 'short' |
| timeframe | VARCHAR(10) | Analysis timeframe |
| entry_price | FLOAT | Planned entry price |
| stop_loss | FLOAT | Stop loss price |
| profit_target | FLOAT | Target price |
| position_size | FLOAT | Number of shares |
| position_value | FLOAT | Dollar value |
| rationale | TEXT | Trade reasoning |
| hypothesis | TEXT | Expected outcome |
| strategy_id | INTEGER | Foreign key to strategies |
| status | VARCHAR(30) | 'draft', 'evaluated', 'executed', 'cancelled' |
| intent_metadata | JSONB | Additional context |
| created_at | TIMESTAMPTZ | Creation time |
| updated_at | TIMESTAMPTZ | Last update time |

### `trade_evaluations`
Evaluation result for a trade intent.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| intent_id | BIGINT | Foreign key to trade_intents |
| campaign_id | BIGINT | Foreign key to position_campaigns |
| leg_id | BIGINT | Foreign key to campaign_legs |
| eval_scope | VARCHAR(20) | 'intent', 'campaign', 'leg' |
| overall_label | VARCHAR(20) | 'aligned', 'mixed', 'fragile', 'deviates' |
| score | FLOAT | Overall score (0-100) |
| summary | TEXT | Evaluation summary |
| blocker_count | INTEGER | Number of blocking issues |
| critical_count | INTEGER | Number of critical issues |
| warning_count | INTEGER | Number of warnings |
| info_count | INTEGER | Number of info items |
| evaluators_run | JSONB | List of evaluators executed |
| evaluated_at | TIMESTAMPTZ | Evaluation timestamp |

### `trade_evaluation_items`
Individual evaluation findings.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| evaluation_id | BIGINT | Foreign key to trade_evaluations |
| evaluator | VARCHAR(100) | Evaluator name |
| code | VARCHAR(50) | Finding code |
| severity | VARCHAR(20) | 'info', 'warning', 'critical', 'blocker' |
| severity_priority | INTEGER | For sorting |
| title | VARCHAR(255) | Finding title |
| message | TEXT | Detailed message |
| dimension_key | VARCHAR(50) | UI grouping key |
| evidence | JSONB | Supporting data |
| visuals | JSONB | Chart render instructions |

## Broker Integration Tables

### `snaptrade_users`
Mapping between internal user and SnapTrade user.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| user_account_id | INTEGER | Foreign key to user_accounts (unique) |
| snaptrade_user_id | VARCHAR(255) | SnapTrade user ID (unique) |
| snaptrade_user_secret | VARCHAR(255) | SnapTrade user secret |
| created_at | TIMESTAMPTZ | Creation time |

### `broker_connections`
Connected brokerage accounts via SnapTrade.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| snaptrade_user_id | INTEGER | Foreign key to snaptrade_users |
| brokerage_name | VARCHAR(100) | Broker name (e.g., 'Robinhood') |
| brokerage_slug | VARCHAR(50) | Broker identifier |
| authorization_id | VARCHAR(255) | SnapTrade authorization (unique) |
| meta | JSONB | Connection metadata |
| is_active | BOOLEAN | Connection status |
| created_at | TIMESTAMPTZ | Creation time |
| updated_at | TIMESTAMPTZ | Last update time |

### `trade_fills`
Executed trade fills synced from brokers (immutable ledger).

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| broker_connection_id | INTEGER | Foreign key to broker_connections |
| account_id | INTEGER | Foreign key to user_accounts |
| symbol | VARCHAR(20) | Stock symbol |
| side | VARCHAR(10) | 'buy' or 'sell' |
| quantity | FLOAT | Number of shares |
| price | FLOAT | Execution price |
| fees | FLOAT | Trading fees |
| executed_at | TIMESTAMPTZ | Execution timestamp |
| broker | VARCHAR(100) | Broker name |
| asset_type | VARCHAR(20) | 'equity', 'option', 'crypto' |
| currency | VARCHAR(10) | 'USD' |
| order_id | VARCHAR(255) | Broker order ID |
| venue | VARCHAR(100) | Execution venue |
| external_trade_id | VARCHAR(255) | Broker trade ID (unique) |
| source | VARCHAR(20) | 'broker_synced', 'manual' |
| import_batch_id | BIGINT | Import batch identifier |
| intent_id | BIGINT | Foreign key to trade_intents |
| raw_data | JSONB | Raw broker data |
| created_at | TIMESTAMPTZ | Creation time |

## Trade Lifecycle Tables

### `decision_contexts`
Trader's context and feelings attached 1-to-1 with a trade fill.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| account_id | INTEGER | Foreign key to user_accounts |
| fill_id | BIGINT | Foreign key to trade_fills (unique) |
| context_type | VARCHAR(30) | 'entry', 'add', 'reduce', 'exit', 'idea', 'post_trade_reflection' |
| strategy_id | INTEGER | Foreign key to strategies |
| hypothesis | TEXT | Trade hypothesis |
| exit_intent | JSONB | Planned exit conditions |
| feelings_then | JSONB | Emotions at decision time |
| feelings_now | JSONB | Current reflection |
| notes | TEXT | Additional notes |
| created_at | TIMESTAMPTZ | Creation time |
| updated_at | TIMESTAMPTZ | Last update time |

### `campaign_checks`
Behavioral nudge checks attached to decision contexts.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| decision_context_id | BIGINT | Foreign key to decision_contexts |
| account_id | INTEGER | Foreign key to user_accounts |
| check_type | VARCHAR(50) | Check identifier |
| severity | VARCHAR(10) | 'info', 'warn', 'critical' |
| passed | BOOLEAN | Whether check passed |
| details | JSONB | Check details |
| nudge_text | TEXT | Human-readable nudge message |
| acknowledged | BOOLEAN | Whether trader acknowledged |
| trader_action | VARCHAR(20) | 'proceeded', 'modified', 'cancelled' |
| checked_at | TIMESTAMPTZ | Check timestamp |
| check_phase | VARCHAR(20) | 'pre_trade', 'at_entry', 'during', 'at_exit', 'post_trade' |

### `campaign_fills`
Self-contained campaign grouping. Campaigns are derived from fills using FIFO zero-crossing. `group_id` is the first fill_id in the campaign (deterministic, unique per campaign). A fill can appear in two groups when a zero-crossing flip occurs.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key (surrogate row key) |
| group_id | BIGINT | First fill_id in the group (campaign identifier) |
| fill_id | BIGINT | Foreign key to trade_fills |
| created_at | TIMESTAMPTZ | When the row was created (rebuild timestamp) |

Constraints: UNIQUE on (group_id, fill_id), indexes on group_id and fill_id.

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

## Timezone Handling

### Storage Format

All timestamps in the database are stored as **timezone-aware UTC** using PostgreSQL's `TIMESTAMPTZ` type. This ensures consistent time handling across different data sources and client applications.

### Import Behavior

When importing data from CSV or Parquet files:

1. **Timezone-naive timestamps** (common in most CSV/Parquet files) are automatically converted to UTC
2. **Timezone-aware timestamps** are normalized to UTC before storage
3. The `DatabaseLoader.import_csv()` and `import_parquet()` methods handle this conversion automatically

### Code Example

```python
# The loader automatically handles timezone conversion
from src.data.loaders import DatabaseLoader

loader = DatabaseLoader()

# CSV files with naive timestamps work correctly
rows = loader.import_csv("data/raw/AAPL.csv", "AAPL", timeframe="1Min")

# Parquet files are also handled
rows = loader.import_parquet("data/raw/WTI.parquet", "WTI", timeframe="1Day")
```

### Technical Details

The import methods convert pandas timestamps to timezone-aware UTC:

```python
import pytz

# Convert naive timestamp to UTC
if timestamp.tzinfo is None:
    timestamp = pytz.UTC.localize(timestamp)
```

This ensures compatibility between:
- Pandas DataFrames (often timezone-naive)
- PostgreSQL TIMESTAMPTZ columns (always timezone-aware)
- The sync log tracking (requires timezone-aware comparisons)

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
