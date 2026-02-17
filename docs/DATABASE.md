# Database Schema & Configuration

PostgreSQL database schema and configuration for the Trading Buddy platform.

## Schema Overview

The database consists of five main domains:

1. **Market Data** - OHLCV bars, features, sync tracking
2. **User Management** - Accounts, profiles, custom rules, waitlist
3. **Strategies** - User-defined and benchmark trading strategies, strategy probes
4. **Trade Lifecycle** - Fills, decision contexts, campaign checks, campaign groupings
5. **Broker Integration** - SnapTrade users, broker connections

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
| timeframe | VARCHAR(10) | '1Min', '15Min', '1Hour', '1Day' |
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
| phone | VARCHAR(50) | Phone number (optional) |
| address | TEXT | Address (optional) |
| date_of_birth | DATE | Date of birth (optional) |
| gender | VARCHAR(20) | Gender (optional) |
| is_active | BOOLEAN | Account status |
| created_at | TIMESTAMPTZ | Creation time |
| updated_at | TIMESTAMPTZ | Last update time |

### `user_profiles`
Trading, risk, and site preferences (one-to-one with user_accounts). Uses JSONB columns for flexible storage.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| user_account_id | INTEGER | Foreign key to user_accounts (unique) |
| profile | JSONB | Trading profile (account_balance, default_timeframes, experience_level, trading_style, primary_markets, account_size_range, evaluation_controls) |
| risk_profile | JSONB | Risk preferences (max_position_size_pct, max_risk_per_trade_pct, max_daily_loss_pct, min_risk_reward_ratio, max_open_positions, stop_loss_required) |
| site_prefs | JSONB | UI preferences (theme, sidebar_collapsed, notifications_enabled, language) |
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

### `waitlist`
Users requesting platform access. Status is managed via direct DB update (no admin UI).

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| name | VARCHAR(255) | User's name |
| email | VARCHAR(255) | Email address (unique) |
| status | VARCHAR(20) | 'waiting', 'approved', 'rejected' |
| referral_source | VARCHAR(255) | How user heard about the platform |
| notes | TEXT | Admin notes |
| created_at | TIMESTAMPTZ | Creation time |
| updated_at | TIMESTAMPTZ | Last update time |

## Strategy Tables

### `strategies`
User-defined and benchmark trading strategies. Names are unique per account.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| account_id | INTEGER | Foreign key to user_accounts |
| name | VARCHAR(100) | Strategy name (unique per account) |
| description | TEXT | Strategy description |
| direction | VARCHAR(10) | 'long', 'short', or 'both' |
| timeframes | JSONB | Applicable timeframes (e.g., '["1Day", "1Hour"]') |
| entry_criteria | TEXT | Entry rules description |
| exit_criteria | TEXT | Exit rules description |
| max_risk_pct | FLOAT | Max risk per trade (%) |
| min_risk_reward | FLOAT | Min risk/reward ratio |
| is_active | BOOLEAN | Whether strategy is active |
| risk_profile | JSONB | Strategy-specific risk overrides |
| implied_strategy_family | VARCHAR(50) | Auto-detected strategy theme (trend, breakout, momentum, mean_reversion, volatility) |
| created_at | TIMESTAMPTZ | Creation time |
| updated_at | TIMESTAMPTZ | Last update time |

### `probe_strategies`
Strategy catalog for the 100-strategy probe system.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| name | VARCHAR(100) | Strategy name (unique) |
| display_name | VARCHAR(200) | Human-readable display name |
| philosophy | VARCHAR(500) | Strategy philosophy description |
| strategy_type | VARCHAR(50) | Strategy type classification |
| direction | VARCHAR(15) | 'long', 'short', or 'both' |
| details | JSONB | Full strategy configuration |
| is_active | BOOLEAN | Whether strategy is active |
| created_at | TIMESTAMPTZ | Creation time |
| updated_at | TIMESTAMPTZ | Last update time |

### `strategy_probe_results`
Aggregated probe result storage for backtested strategies.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| run_id | VARCHAR(50) | Probe run identifier |
| symbol | VARCHAR(20) | Tested symbol |
| strategy_id | INTEGER | Foreign key to probe_strategies |
| period_start | TIMESTAMPTZ | Backtest period start |
| period_end | TIMESTAMPTZ | Backtest period end |
| open_day | DATE | Trading day |
| total_trades | INTEGER | Number of trades |
| win_rate | FLOAT | Win percentage |
| profit_factor | FLOAT | Gross profit / gross loss |
| total_pnl | FLOAT | Total P&L |
| max_drawdown | FLOAT | Maximum drawdown |
| sharpe_ratio | FLOAT | Sharpe ratio |
| metrics | JSONB | Additional metrics |
| created_at | TIMESTAMPTZ | Creation time |

### `strategy_probe_trades`
Individual trades from strategy probe runs.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| result_id | BIGINT | Foreign key to strategy_probe_results |
| symbol | VARCHAR(20) | Traded symbol |
| side | VARCHAR(10) | 'long' or 'short' |
| entry_time | TIMESTAMPTZ | Entry timestamp |
| exit_time | TIMESTAMPTZ | Exit timestamp |
| entry_price | FLOAT | Entry price |
| exit_price | FLOAT | Exit price |
| quantity | FLOAT | Position size |
| pnl | FLOAT | Trade P&L |
| return_pct | FLOAT | Trade return percentage |
| exit_reason | VARCHAR(50) | Why the trade was exited |
| metrics | JSONB | Additional trade metrics |
| created_at | TIMESTAMPTZ | Creation time |

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
| external_trade_id | VARCHAR(255) | Broker trade ID (unique per account) |
| source | VARCHAR(20) | 'broker_synced', 'manual' |
| import_batch_id | BIGINT | Import batch identifier |
| raw_data | JSONB | Raw broker data |
| created_at | TIMESTAMPTZ | Creation time |

## Trade Lifecycle Tables

### `decision_contexts`
Trader's context and feelings attached 1-to-1 with a trade fill.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| account_id | INTEGER | Foreign key to user_accounts |
| fill_id | BIGINT | Foreign key to trade_fills (unique, NOT NULL) |
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
| decision_context_id | BIGINT | Foreign key to decision_contexts (NOT NULL) |
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

## Journal Tables

### `journal_entries`
User journal entries for trade reflection and discipline tracking.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| account_id | INTEGER | Foreign key to user_accounts |
| date | VARCHAR(10) | Entry date (YYYY-MM-DD) |
| entry_type | VARCHAR(30) | Type of journal entry |
| content | TEXT | Journal entry content |
| trade_id | VARCHAR(50) | Optional associated trade ID |
| tags | JSONB | Entry tags |
| mood | VARCHAR(20) | Trader mood at time of entry |
| created_at | TIMESTAMPTZ | Creation time |
| updated_at | TIMESTAMPTZ | Last update time |

## Dropped Tables (Removed in Migration 026)

The following tables were removed as part of the trade lifecycle restructuring:

- **`trade_intents`** - User's proposed trade for evaluation (replaced by fills + decision contexts)
- **`trade_evaluations`** - Evaluation result for a trade intent
- **`trade_evaluation_items`** - Individual evaluation findings
- **`position_campaigns`** - Campaign tracking (replaced by campaign_fills grouping)
- **`campaign_legs`** - Campaign leg tracking
- **`leg_fill_map`** - Leg-to-fill junction table
- **`position_lots`** - Position lot tracking
- **`lot_closures`** - Lot closure matching

The simplified model treats fills as the atomic unit, with decision_contexts capturing trader reasoning per fill and campaign_fills providing derived groupings.

## Migrations

Alembic is used for database migrations. The project currently has 31 migrations (001-031).

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

### Migration History

| Migration | Description |
|-----------|-------------|
| 001 | Initial schema (tickers, ohlcv_bars, data_sync_log) |
| 002 | Add computed_features table |
| 003 | Remove VWAP column |
| 004 | Consolidate states to features |
| 005 | Trading Buddy tables (trade_intents, evaluations, user_accounts/rules) |
| 006 | Broker integration tables (snaptrade_users, broker_connections, trade_fills) |
| 007 | Auth and user_profiles (split from user_accounts) |
| 008 | Trade lifecycle schema (position_lots, lot_closures, decision_contexts) |
| 009 | Position campaigns and campaign legs |
| 010 | Strategies as first-class entity |
| 011 | User profiles JSONB restructure |
| 012 | Strategy risk profiles |
| 013 | Strategy config columns and journal_entries table |
| 014 | Site preferences (site_prefs JSONB on user_profiles) |
| 015 | Strategy probe tables (probe_strategies, strategy_probe_results) |
| 016 | Strategy probe trades |
| 017 | Add trade P&L metrics |
| 018 | Fix open_day to date type |
| 019 | Campaign checks table |
| 020 | Add strategy versioning |
| 021 | Add probe results open_day index |
| 022 | Campaign leg orphan support |
| 023 | Drop campaign strategy_id |
| 024 | Rename severity 'block' to 'critical' |
| 025 | Remove 'danger' severity |
| 026 | Restructure trade lifecycle (drop intents, lots, old campaigns) |
| 027 | Drop campaigns table, self-contained campaign_fills |
| 028 | Make campaign_checks.decision_context_id NOT NULL |
| 029 | Add implied_strategy_family to strategies |
| 030 | Waitlist table |
| 031 | Seed app user and benchmark strategies |

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
           |
           v
    +--------------+
    | DB has data  |
    | Jan 1-10     |
    +--------------+
           |
           v
    +--------------+
    | Fetch Alpaca |
    | Jan 11-15    |  <-- Only fetches missing data
    +--------------+
           |
           v
    +--------------+
    | Return full  |
    | Jan 1-15     |
    +--------------+
```

## Performance

### Indexes

The following indexes are created for query performance:

- `ix_tickers_symbol` - Fast symbol lookup
- `ix_ohlcv_ticker_timeframe_ts` - Primary query pattern
- `ix_ohlcv_timestamp` - Time-based queries
- `ix_decision_contexts_account_fill` - Decision context lookup by account and fill
- `ix_campaign_checks_decision_context` - Check lookup by decision context
- `ix_campaign_fills_group_id` - Campaign group lookup
- `ix_campaign_fills_fill_id` - Fill-to-campaign lookup
- `ix_strategies_account_id` - Strategy lookup by account

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
- Check constraint on campaign_checks.severity: IN ('info', 'warn', 'critical')
- Check constraint on campaign_checks.check_phase: IN ('pre_trade', 'at_entry', 'during', 'at_exit', 'post_trade')
- Check constraint on decision_contexts.context_type
- Check constraint on trade_fills.side: IN ('buy', 'sell')
- Unique constraint on (account_id, external_trade_id) for trade_fills
- Unique constraint on (group_id, fill_id) for campaign_fills
- Unique constraint on (account_id, name) for strategies

### Cascading Deletes

Deleting a ticker automatically removes:
- All associated OHLCV bars
- All sync log entries

Deleting a user account removes:
- User profile
- User rules
- Decision contexts (and their campaign checks via cascade)
- Strategy associations are SET NULL
