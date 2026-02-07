# TradingBuddy Trade Data Model

This document describes the broker-agnostic schema for modeling trades in the **TradingBuddy** platform.
The goal is to correctly handle real-world trading behavior such as partial fills, scaling in/out, long & short trades, and position flips, while keeping the system explainable for users and coaches.

---

## Core Design Principle

**Do not overload the word _trade_.**

Instead:
- Store **what actually happened** as immutable transactions (fills).
- Model **exposure** via lots (positions).
- Pair opens and closes via a matching table.
- Derive human-friendly "trades" (round-trips) for analytics and UI.

This avoids edge cases where:
- Buy quantity ≠ sell quantity
- One order both closes and opens a position
- Users scale in/out over time
- Shorts and flips occur

---

## Conceptual Layers

| Layer | Purpose | Mutable |
|---|---|---|
| Trade Fills | Broker truth / ledger | No |
| Position Lots | Inventory & cost basis | Yes |
| Lot Closures | Open ↔ Close pairing | Yes |
| Round Trips | User-visible "trade" | Derived |

---

## Implementation Notes

The implementation uses the following conventions consistent with the existing codebase:

- **Primary keys**: `BigInteger` autoincrement (not UUID)
- **Financial fields**: `Float` (not `Numeric`)
- **Enum values**: Lowercase strings (`'buy'`/`'sell'`, `'long'`/`'short'`, `'fifo'`/`'lifo'`)
- **Timestamps**: `DateTime(timezone=True)`

---

## 1. `trade_fills` (Immutable Ledger)

**One row per executed fill** (or execution).

This is the canonical source of truth and mirrors broker data. Evolved from the original `trade_histories` table.

### Schema

| Column | Type | Constraints |
|---|---|---|
| `id` | BigInteger | PK, autoincrement |
| `broker_connection_id` | Integer | FK → broker_connections.id, NOT NULL |
| `account_id` | Integer | FK → user_accounts.id, nullable (for backfill) |
| `symbol` | String(20) | NOT NULL, indexed |
| `side` | String(10) | CHECK ('buy', 'sell') |
| `quantity` | Float | NOT NULL |
| `price` | Float | NOT NULL |
| `fees` | Float | NOT NULL, default 0.0 |
| `executed_at` | DateTime(tz) | NOT NULL, indexed |
| `broker` | String(100) | Brokerage name, nullable |
| `asset_type` | String(20) | equity, option, crypto, nullable |
| `currency` | String(10) | NOT NULL, default 'USD' |
| `order_id` | String(255) | Broker order ID, nullable |
| `venue` | String(100) | Execution venue, nullable |
| `external_trade_id` | String(255) | Unique broker execution ID, nullable |
| `import_batch_id` | BigInteger | Batch import tracking, nullable |
| `intent_id` | BigInteger | FK → trade_intents.id, nullable (bridges pre→post execution) |
| `raw_data` | JSONB | Raw broker payload, default {} |
| `created_at` | DateTime(tz) | NOT NULL |

### Indexes & Constraints
- Unique: `(account_id, external_trade_id)`
- Unique: `external_trade_id` (standalone)
- Index: `(broker_connection_id, symbol)`
- Index: `(account_id, symbol)`
- CHECK: `side IN ('buy', 'sell')`

### Notes
- Never update or delete rows.
- `broker_connection_id` retained for SnapTrade relationship compatibility.
- `account_id` provides direct user linkage without joining through broker_connections → snaptrade_users.
- `intent_id` links post-execution fills back to pre-execution trade intents.
- This table answers: **"What exactly happened?"**

---

## 2. `position_lots` (Inventory / Cost Basis)

**One row per opened lot**, created from an opening fill (or remainder after a flip).

### Schema

| Column | Type | Constraints |
|---|---|---|
| `id` | BigInteger | PK, autoincrement |
| `account_id` | Integer | FK → user_accounts.id, NOT NULL |
| `symbol` | String(20) | NOT NULL, indexed |
| `direction` | String(10) | CHECK ('long', 'short') |
| `opened_at` | DateTime(tz) | NOT NULL |
| `open_fill_id` | BigInteger | FK → trade_fills.id, NOT NULL |
| `open_qty` | Float | NOT NULL, > 0 |
| `remaining_qty` | Float | NOT NULL, >= 0 |
| `avg_open_price` | Float | NOT NULL, > 0 |
| `strategy_tag` | String(100) | nullable |
| `status` | String(10) | CHECK ('open', 'closed'), default 'open', indexed |
| `created_at` | DateTime(tz) | NOT NULL |

### Indexes
- Composite: `(account_id, symbol, status)` for open position lookups

### Notes
- Lots make cost basis and narration explainable.
- FIFO lots are recommended for coaching products.
- `remaining_qty` decreases as the lot is closed.

---

## 3. `lot_closures` (Open ↔ Close Pairing)

This table **solves the pairing problem**.

Each row represents a **partial or full match** between:
- one open lot
- one closing fill
- for a specific quantity

### Schema

| Column | Type | Constraints |
|---|---|---|
| `id` | BigInteger | PK, autoincrement |
| `lot_id` | BigInteger | FK → position_lots.id, NOT NULL, indexed |
| `open_fill_id` | BigInteger | FK → trade_fills.id, NOT NULL |
| `close_fill_id` | BigInteger | FK → trade_fills.id, NOT NULL, indexed |
| `matched_qty` | Float | NOT NULL, > 0 |
| `open_price` | Float | NOT NULL, > 0 |
| `close_price` | Float | NOT NULL, > 0 |
| `realized_pnl` | Float | nullable (computed) |
| `fees_allocated` | Float | nullable |
| `match_method` | String(10) | CHECK ('fifo', 'lifo', 'avg', 'manual'), default 'fifo' |
| `matched_at` | DateTime(tz) | NOT NULL, default now() |

### Why this works
- Supports partial closes
- Supports scale in / scale out
- Handles shorts naturally
- Buy and sell quantities never need to "match" at order level

---

## 4. `round_trips` (Derived "Trade")

This is the **user-facing trade object** shown in UI and analytics.

It is **derived**, not canonical.

### Definition Options
- One fully closed lot = one round trip (default)
- Cluster multiple lots for UX if needed

### Schema

| Column | Type | Constraints |
|---|---|---|
| `id` | BigInteger | PK, autoincrement |
| `account_id` | Integer | FK → user_accounts.id, NOT NULL |
| `symbol` | String(20) | NOT NULL, indexed |
| `direction` | String(10) | CHECK ('long', 'short') |
| `opened_at` | DateTime(tz) | nullable |
| `closed_at` | DateTime(tz) | nullable |
| `qty_opened` | Float | nullable |
| `qty_closed` | Float | nullable |
| `avg_open_price` | Float | nullable |
| `avg_close_price` | Float | nullable |
| `realized_pnl` | Float | nullable |
| `return_pct` | Float | nullable |
| `holding_period_sec` | Integer | nullable |
| `num_fills` | Integer | nullable |
| `tags` | JSONB | default {} |
| `derived_from` | JSONB | default {} (lot_ids, closure_ids for traceability) |
| `created_at` | DateTime(tz) | NOT NULL |

### Indexes
- Composite: `(account_id, symbol)`
- Composite: `(account_id, closed_at)`

### Notes
- Can be rebuilt anytime from lots + closures.
- Safe to cache or materialize.

---

## Position Matching Logic (High Level)

### Normalize Quantity
- BUY  → `+quantity`
- SELL → `-quantity`

### Rules
1. **Same direction as exposure**
   - Create / add to lots
2. **Opposite direction**
   - Close existing lots using FIFO
3. **Flip**
   - Close existing lots fully
   - Remainder opens a new lot in opposite direction

### Example (Flip)
- Long 100 shares
- Sell 150 shares
  - 100 → closes long lot
  - 50 → opens new short lot

---

## Why Not "One Trade = Buy + Sell"?

Because it breaks when:
- Partial exits occur
- Scaling in/out happens
- Shorts are involved
- One execution both closes and opens

The proposed model handles all of these **without hacks**.

---

## Minimal Viable Version (If You Want to Start Lean)

Required:
- `trade_fills`
- `lot_closures`

Optional later:
- `position_lots`
- `round_trips`

You can initially treat each opening fill as a lot, then formalize lots later.

---

## TradingBuddy-Specific Extensions (Future)

- `intent_id` on trade_fills (implemented — bridges pre→post execution)
- `hypothesis` / `setup` tags
- Regime labels (trend, chop, momentum)
- Coaching annotations ("scaled too early", "late entry")

---

## Summary

**Truth lives in fills.
Meaning lives in lots.
Insight lives in round trips.**

This separation keeps TradingBuddy:
- correct
- explainable
- extensible
