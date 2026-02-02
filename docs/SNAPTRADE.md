# SnapTrade Integration

This document describes the integration with [SnapTrade](https://snaptrade.com/) to connect users' brokerage accounts and synchronize trade history.

## Overview

The integration allows users to:
1.  Connect their brokerage accounts via SnapTrade's OAuth-like flow.
2.  Synchronize trade history and holdings.
3.  View unified trade history within the application.

## Configuration

To enable SnapTrade integration, the following environment variables must be set in `.env`:

```env
SNAPTRADE_CLIENT_ID=your_client_id
SNAPTRADE_CONSUMER_KEY=your_consumer_key
```

## Data Models

### `SnapTradeUser`
Maps an internal user ID to a SnapTrade user ID and secret.
- `user_account_id`: Internal user ID.
- `snaptrade_user_id`: SnapTrade user ID.
- `snaptrade_user_secret`: Encrypted user secret from SnapTrade.

### `BrokerConnection`
Represents a connected brokerage account.
- `snaptrade_user_id`: Link to `SnapTradeUser`.
- `authorization_id`: Unique ID for the connection.
- `brokerage_name`: Name of the broker (e.g., "Robinhood").
- `meta`: JSON field for additional metadata.

### `TradeHistory`
Stores synchronized trade data.
- `broker_connection_id`: Link to `BrokerConnection`.
- `symbol`, `side`, `quantity`, `price`: Trade details.
- `executed_at`: Timestamp of execution.
- `external_trade_id`: Unique ID from the broker to prevent duplicates.

## API Endpoints

### Connect Broker
`POST /api/trading-buddy/connect`
Initiates the connection flow. Registers the user if necessary and returns a redirect URL to SnapTrade's connection portal.

### Sync Trades
`POST /api/trading-buddy/sync`
Triggers a synchronization of trade history for the current user. Fetches new trades from connected brokers and stores them in the `trade_histories` table.

### List Trades
`GET /api/trading-buddy/trades`
Returns a paginated list of trade history for the user.

## Frontend Components

- **`BrokerConnect`**: A React component that provides a button to initiate the connection flow. It handles the API call and redirects the user.
- **`TradeHistoryTable`**: A React component that displays the synchronized trade history in a tabular format and allows manual triggering of a sync.
