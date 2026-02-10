# Position Campaigns (Multi-Leg Trades) — UI + Schema Plan
*(Trading Buddy / evaluation-first platform)*

This document defines a **detailed implementation plan** for supporting **multi-leg trading journeys** like:

- Buy 100 AAPL
- Buy 50 AAPL (add)
- Sell 150 AAPL (close)

…and evaluating the **decision points** (open/add/reduce/exit) without turning your product into a broker terminal.

It **builds on** the existing trade lifecycle schema (migrations 005–008) by evolving existing tables and adding genuinely new ones where gaps exist.

> **Trade Fills (atomic truth) → Position Campaigns (what users see) → Decision Points (what you evaluate)**

---

## 0) Goals and Non-Goals

### Goals
- Represent real-world trading behavior: scale-in, scale-out, partials, adds, and closes.
- Show both "legs" (entry & exit) **plus intermediate adds/reductions**.
- Evaluate **each decision point** in its own context (regime, timing, behavior).
- Keep UI friendly and consistent across:
  - historical trades (synced/manual)
  - proposed trades (pre-trade evaluation)
- Provide correct P&L / cost basis while allowing user-friendly defaults.

### Non-goals (Phase 1)
- Full order management / routing / live execution.
- Deep options strategy modeling (spreads, multi-leg options) — later phase.
- Tick-level microstructure analytics.

---

## 1) Canonical Domain Model

### Layer A — Fill Ledger (Atomic Truth)
A **TradeFill** is a fill (or normalized fill) from the broker. Immutable.
*(Existing table: `trade_fills` — migration 008)*

### Layer B — Position Campaign (User-Facing "Trade Journey")
A **PositionCampaign** is the unit the user sees in history:
"the time between opening a position and returning to flat (0)."
*(Evolved from existing `round_trips` table — migration 009)*

### Layer C — Legs & Decision Points (Evaluation Units)
A **CampaignLeg** is a grouped set of fills for a single intent (open/add/reduce/close).
A **DecisionContext** is where the trader records context/feelings at a decision point, usually 1:1 with a Leg.

**In the example:**
- Decision #1: Open +100
- Decision #2: Add +50
- Decision #3: Exit −150

---

## 2) Table Schema (PostgreSQL)

> **Key design:** keep raw broker truth separate from derived "campaigns" and evaluations.
> All tables follow codebase conventions: BigInteger PKs with autoincrement, Float for financial fields, DateTime(timezone=True) timestamps, lowercase strings in CHECK constraints.

### Existing Tables — Kept As-Is

These tables already exist and need no schema changes for campaign support:

| Table | Role | Migration |
|---|---|---|
| `snaptrade_users` | SnapTrade user mapping | 006 |
| `broker_connections` | Connected brokerage accounts | 006 |
| `lot_closures` | Open↔close lot pairing for P&L | 008 |

### Existing Tables — Evolved (Minor Additions)

These tables exist but receive new columns in migration 009:

#### 2.1 `trade_fills` (add `source`)
Atomic fills synced from brokers. Immutable after insert.

| New Column | Type | Notes |
|---|---|---|
| `source` | String(20), default 'broker_synced' | CHECK ('broker_synced', 'manual', 'proposed') |

*All existing columns retained. See migration 008 for full schema.*

#### 2.2 `position_lots` (add `campaign_id`)
Open position inventory and cost basis.

| New Column | Type | Notes |
|---|---|---|
| `campaign_id` | BigInteger, FK → position_campaigns.id, nullable | Links lot to its campaign |

#### 2.3 `trade_intents` (add behavioral fields)
User trade proposals for evaluation.

| New Column | Type | Notes |
|---|---|---|
| `hypothesis` | Text, nullable | What must be true for this trade |
| `strategy_id` | Integer FK → strategies.id, nullable | Normalized strategy reference (migration 010) |

*Note: `strategy_tags` (JSONB) was added in migration 009 and replaced by `strategy_id` FK in migration 010.*

#### 2.4 `trade_evaluations` (multi-scope support)
Evaluation results. Evolves from 1:1 intent binding to multi-scope.

| Change | Type | Notes |
|---|---|---|
| `intent_id` | Make nullable | Remove UNIQUE constraint |
| `campaign_id` | BigInteger FK → position_campaigns.id, nullable | NEW |
| `leg_id` | BigInteger FK → campaign_legs.id, nullable | NEW |
| `eval_scope` | String(20), default 'intent' | CHECK ('intent', 'campaign', 'leg') |
| `overall_label` | String(20), nullable | 'aligned', 'mixed', 'fragile', 'deviates' |

Partial unique indexes enforce one evaluation per scope target.

#### 2.5 `trade_evaluation_items` (add dimension and visuals)
Individual evaluation findings.

| New Column | Type | Notes |
|---|---|---|
| `dimension_key` | String(50), nullable | Groups items by business dimension (regime_fit, timing, etc.) |
| `visuals` | JSONB, nullable | Chart render instructions (see Section 6) |

---

### New Tables

#### 2.6 `position_campaigns` (evolved from `round_trips`)
Derived object representing a "trade journey" from flat → flat.
Table renamed from `round_trips` in migration 009; all existing columns kept.

| Column | Type | Notes |
|---|---|---|
| `id` | BigInteger | PK, autoincrement |
| `account_id` | Integer, FK → user_accounts.id | NOT NULL |
| `symbol` | String(20) | NOT NULL |
| `direction` | String(10) | CHECK ('long', 'short') |
| `opened_at` | DateTime(tz), nullable | First fill opening non-zero |
| `closed_at` | DateTime(tz), nullable | When position returns to 0 |
| `qty_opened` | Float, nullable | Abs qty at open (initial leg) |
| `qty_closed` | Float, nullable | Abs qty at close |
| `avg_open_price` | Float, nullable | Average cost after first leg |
| `avg_close_price` | Float, nullable | Avg cost at close |
| `realized_pnl` | Float, nullable | Cached, recomputable |
| `return_pct` | Float, nullable | Percentage return |
| `holding_period_sec` | Integer, nullable | Duration in seconds |
| `num_fills` | Integer, nullable | Total fill count |
| `tags` | JSONB | Strategy tags, labels, annotations |
| `derived_from` | JSONB | Traceability: lot_ids, closure_ids |
| `created_at` | DateTime(tz) | NOT NULL |
| **New columns below** | | |
| `status` | String(10), default 'open' | CHECK ('open', 'closed') |
| `max_qty` | Float, nullable | Peak absolute position |
| `cost_basis_method` | String(10), default 'average' | CHECK ('average', 'fifo', 'lifo') |
| `source` | String(20), default 'broker_synced' | CHECK ('broker_synced', 'manual', 'proposed') |
| `link_group_id` | BigInteger, nullable | Cross-account grouping |
| `r_multiple` | Float, nullable | PnL / initial risk |
| `intent_id` | BigInteger, FK → trade_intents.id, nullable | Originating intent |
| `strategy_id` | Integer, FK → strategies.id, nullable | Normalized strategy reference (migration 010) |
| `updated_at` | DateTime(tz) | Campaigns are mutable |

**Indexes**
- (account_id, symbol) — existing
- (account_id, closed_at) — existing
- (account_id, status) — new

#### 2.7 `campaign_legs` (NEW)
A leg groups one or more trade fills that share the same intent.

| Column | Type | Notes |
|---|---|---|
| `id` | BigInteger | PK, autoincrement |
| `campaign_id` | BigInteger, FK → position_campaigns.id | NOT NULL |
| `leg_type` | String(20) | CHECK ('open', 'add', 'reduce', 'close', 'flip_close', 'flip_open') |
| `side` | String(10) | CHECK ('buy', 'sell') |
| `quantity` | Float | NOT NULL |
| `avg_price` | Float, nullable | Weighted avg from fills |
| `started_at` | DateTime(tz) | NOT NULL |
| `ended_at` | DateTime(tz), nullable | |
| `fill_count` | Integer, default 1 | Number of fills in this leg |
| `intent_id` | BigInteger, FK → trade_intents.id, nullable | Originating intent for this leg |
| `notes` | Text, nullable | User notes |
| `created_at` | DateTime(tz) | NOT NULL |

**Indexes**
- (campaign_id, started_at)

#### 2.8 `leg_fill_map` (NEW — join table)
Maps legs to the trade fills that compose them. Supports partial allocation.

| Column | Type | Notes |
|---|---|---|
| `leg_id` | BigInteger, FK → campaign_legs.id | PK part 1 |
| `fill_id` | BigInteger, FK → trade_fills.id | PK part 2 |
| `allocated_qty` | Float, nullable | For partial allocation |

Composite PK: `(leg_id, fill_id)`.

#### 2.9 `decision_contexts` (NEW)
Stores trader-provided context at a decision moment (entry/add/exit).

| Column | Type | Notes |
|---|---|---|
| `id` | BigInteger | PK, autoincrement |
| `account_id` | Integer, FK → user_accounts.id | NOT NULL |
| `campaign_id` | BigInteger, FK → position_campaigns.id, nullable | |
| `leg_id` | BigInteger, FK → campaign_legs.id, nullable | |
| `intent_id` | BigInteger, FK → trade_intents.id, nullable | |
| `context_type` | String(30) | CHECK ('entry', 'add', 'reduce', 'exit', 'idea', 'post_trade_reflection') |
| `strategy_id` | Integer FK → strategies.id, nullable | Normalized strategy reference (migration 010) |
| `hypothesis` | Text, nullable | What must be true |
| `exit_intent` | JSONB, nullable | Exit plan details |
| `feelings_then` | JSONB, nullable | Emotion chips at decision time |
| `feelings_now` | JSONB, nullable | Post-trade reflection emotion |
| `notes` | Text, nullable | |
| `created_at` | DateTime(tz) | NOT NULL |
| `updated_at` | DateTime(tz) | NOT NULL |

**Indexes**
- (account_id, campaign_id)
- (account_id, created_at)

#### 2.10 `strategies` (NEW — migration 010)
Normalized, user-scoped strategy entity. Replaces free-text strategy tags with an FK-enforced reference.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | PK, autoincrement |
| `account_id` | Integer, FK → user_accounts.id | NOT NULL, CASCADE |
| `name` | String(100) | NOT NULL |
| `description` | Text, nullable | Free-text description |
| `is_active` | Boolean, default true | Soft-delete support |
| `created_at` | DateTime(tz) | NOT NULL |
| `updated_at` | DateTime(tz) | NOT NULL |

**Constraints**: UNIQUE(account_id, name)
**Indexes**: (account_id)

Referenced by: `position_lots.strategy_id`, `trade_intents.strategy_id`, `decision_contexts.strategy_id`, `position_campaigns.strategy_id` — all with `ondelete="SET NULL"`.

---

### Final Table Roles (no overlap)

| Layer | Table | Unique Role |
|---|---|---|
| Fill Ledger | `trade_fills` | Immutable atomic fill from broker/manual |
| Accounting | `position_lots` | Cost basis inventory per lot |
| Accounting | `lot_closures` | Open↔close lot pairing for P&L |
| Journey | `position_campaigns` | User-visible trade journey (flat→flat) |
| Journey | `campaign_legs` | Semantic decision points within journey |
| Journey | `leg_fill_map` | Join table: which fills compose which legs |
| Pre-execution | `trade_intents` | Structured trade proposals for evaluation |
| Behavioral | `decision_contexts` | Trader's context/feelings at decisions |
| Taxonomy | `strategies` | Normalized user-defined strategies (FK-enforced) |
| Evaluation | `trade_evaluations` | Evaluation results (multi-scope: intent/campaign/leg) |
| Evaluation | `trade_evaluation_items` | Individual findings with dimensions/visuals |

---

## 3) Campaign Construction Rules (From Trade Fills)

### 3.1 Core grouping algorithm (equity, single symbol)
Maintain running position quantity per (account_id, symbol):

- Start new campaign when position transitions **0 → non-zero**
- Campaign remains open while abs(position) > 0
- Add legs when trade fills increase abs(position)
- Reduce legs when trade fills decrease abs(position)
- Close campaign when position transitions **non-zero → 0**

### 3.2 Leg formation (to avoid "one fill = one leg")
Group trade fills into a single leg if:
- same symbol, same side
- within a short window (e.g., 5 minutes) **OR**
- same broker `order_id`

Leg types:
- **open**: first trade fill that creates non-zero
- **add**: increases abs position
- **reduce**: decreases abs position but not to 0
- **close**: brings position to 0
- **flip_close / flip_open**: if a sell crosses through 0 into short (split into close + new campaign open)

### 3.3 Cost basis and P&L
Support:
- **average** (default for UX simplicity)
- fifo/lifo (optional)

Store method at campaign level (`position_campaigns.cost_basis_method`); compute realized P&L accordingly.

---

## 4) UI Plan — Pages and Components

### 4.1 Trades List becomes "Campaigns List"
Route: `/app/trades`

**Row shows (one per campaign):**
- Symbol, direction, opened_at → closed_at
- #legs (e.g., "3 legs")
- max position size
- overall evaluation label (Aligned/Mixed/Fragile/Deviates)
- key flags chips (e.g., "Exit early", "Regime mismatch")
- tiny inline "journey" mini-bar (open dot → close dot with add markers)

**Filters**
- status: open/closed
- source: synced/manual/proposed
- flagged: yes/no
- strategy tag

Click row → `/app/trade/{campaign_id}`

---

### 4.2 Campaign Detail: `/app/trade/{campaign_id}`
Core view.

#### A) Header (always visible)
- `AAPL (Long)` • Opened Feb 1 • Closed Feb 6 • 3 legs
- Overall: `Mixed` (neutral)
- Quick actions: Add context • Mark reviewed • Export

#### B) Trade Journey Timeline (top module)
A horizontal timeline with anchors:

- ● Open (+100)
- ● Add (+50)
- ● Close (−150)

Click an anchor → focuses that decision point.

#### C) Tabs: Campaign vs Decision Points
Tabs:
- Campaign Summary
- Decision: Open
- Decision: Add #1
- Decision: Close

#### D) Evaluation Explorer (cards)
For the selected tab, show `trade_evaluation_items` grouped by `dimension_key` as cards:
- Regime Fit
- Timing (entry or exit)
- Exit Logic (for reduce/close)
- Risk Structure
- Behavioral Signals
- Strategy Consistency

Each card:
- 1-line takeaway
- severity
- expand → explanation + evidence + visuals

#### E) Visual Panel (contextual)
Max 2 visuals visible. Examples:
- price snapshot centered on the selected decision point
- MAE/MFE "risk path" for campaign summary
- behavioral clustering timeline

#### F) Context Capture Panel (lightweight)
Collapsible "Add context" widget for the selected decision point.
Persists to `decision_contexts` table:
- Strategy tags (chips)
- Hypothesis (1–2 lines)
- Exit intent (for close)
- Feelings then (chips + intensity)
- Feelings now (post-trade reflection)
- Notes

Autosave; editable later.

---

### 4.3 Evaluate Proposed Trade: `/app/evaluate`
Creates a `trade_intent` and a `trade_evaluation` with `eval_scope='intent'`.

Recommended:
- Keep the proposed trade as `trade_intent` until a real execution appears.
- When broker sync detects first execution for that symbol, offer "Link to this idea?" (manual confirmation).

---

## 5) Evaluation Engine Adjustments for Multi-Leg

### 5.1 Evaluate at multiple scopes
`trade_evaluations.eval_scope` determines the scope:

1) **Intent scope** (`eval_scope='intent'`)
- Pre-execution evaluation of a trade proposal
- `intent_id` is set, `campaign_id` and `leg_id` are NULL

2) **Campaign scope** (`eval_scope='campaign'`)
- Regime suitability over holding period
- Management quality (MAE/MFE vs stop plan)
- Position building discipline (adds/reduces)
- Behavior patterns across the journey
- `campaign_id` is set

3) **Leg/Decision scope** (`eval_scope='leg'`)
- Entry timing (open/add)
- Exit timing & logic (reduce/close)
- Behavior/emotion at that moment
- Strategy consistency at that moment
- `leg_id` is set

### 5.2 Avoid hindsight bias
- Entry evaluations must not use post-entry future price movement.
- Exit evaluations must not use post-exit future price movement.
- Campaign summary can reference the whole journey, clearly labeled as "in-trade view".

---

## 6) Visual Specification (store instructions in `trade_evaluation_items.visuals`)

Store **render instructions** rather than images.

Example:
```json
{
  "type": "price_snapshot",
  "symbol": "AAPL",
  "timeframe": "15m",
  "center_ts": "2026-02-01T18:35:00Z",
  "overlays": [
    {"kind": "marker", "label": "Open +100", "ts": "...", "price": 182.10},
    {"kind": "line", "label": "VWAP", "series": "vwap"}
  ],
  "window_bars": 120
}
```

Other visual types:
- `risk_path` (MAE/MFE bands, stop/target)
- `behavior_timeline` (after-loss sequences, burst trading)
- `similar_campaigns_strip` (small multiples)

Rules:
- Max 2 visuals visible at once
- Each visual answers one question

---

## 7) Migration Plan

Migration `009_position_campaigns.py` evolves the existing schema:

1. Add `source` column to `trade_fills`
2. Add `hypothesis`, `strategy_tags` to `trade_intents` *(strategy_tags later replaced by strategy_id FK in migration 010)*
3. Rename `round_trips` → `position_campaigns`, add new columns, rename indexes/constraints
4. Create `campaign_legs` table
5. Create `leg_fill_map` table
6. Create `decision_contexts` table
7. Add `campaign_id` to `position_lots`
8. Evolve `trade_evaluations`: make `intent_id` nullable, drop UNIQUE, add `campaign_id`, `leg_id`, `eval_scope`, `overall_label`, add partial unique indexes
9. Add `dimension_key`, `visuals` to `trade_evaluation_items`

Full downgrade reversal in reverse order.

Migration `010_strategies_first_class.py` normalizes strategy:

1. Create `strategies` table (unique name per account)
2. Add `strategy_id` FK to `position_lots`, drop `strategy_tag`
3. Add `strategy_id` FK to `trade_intents`, drop `strategy_tags`
4. Add `strategy_id` FK to `decision_contexts`, drop `strategy_tags`
5. Add `strategy_id` FK to `position_campaigns`

---

## 8) Implementation Roadmap

### Phase A — Schema + Models (This Plan)
1. Migration 009: evolve and create tables
2. ORM models: rename RoundTrip → PositionCampaign, add CampaignLeg, LegFillMap, DecisionContext
3. Update repository with CRUD methods for new models

### Phase B — Campaign Builder (Backend)
4. Campaign builder service: position tracking, open/close from fills
5. Leg grouping logic (order_id / time window)
6. Compute derived metrics (avg cost, pnl, max_qty)

### Phase C — Evaluation Engine
7. Multi-scope evaluation: campaign + leg scope evaluators
8. Populate evidence + visuals instructions
9. Decision context capture service

### Phase D — UI (Next.js Portal)
10. Campaigns list (/app/trades)
11. Campaign detail (/app/trade/[id]) with timeline anchors
12. Context capture widget (autosave)
13. Evaluate page (/app/evaluate) producing trade_intent + evaluation

### Phase E — Broker Integrations
14. Settings → brokers connect/sync UI
15. Sync jobs → fills → campaigns

### Phase F — Polish
16. "Explain this flag" with evidence references
17. Export campaign review (optional)

---

## 9) Suggested API Shapes (Frontend-Friendly)

### Campaign list
`GET /api/campaigns`
```json
{
  "items": [
    {
      "id": 1,
      "symbol": "AAPL",
      "direction": "long",
      "status": "closed",
      "openedAt": "...",
      "closedAt": "...",
      "legsCount": 3,
      "overallLabel": "mixed",
      "keyFlags": ["exit_early", "regime_mismatch"],
      "realizedPnl": 150.00,
      "source": "broker_synced"
    }
  ]
}
```

### Campaign detail
`GET /api/campaigns/{id}`
```json
{
  "campaign": {
    "id": 1,
    "symbol": "AAPL",
    "direction": "long",
    "status": "closed",
    "openedAt": "...",
    "closedAt": "...",
    "qtyOpened": 100,
    "maxQty": 150,
    "avgOpenPrice": 182.10,
    "realizedPnl": 150.00,
    "costBasisMethod": "average",
    "source": "broker_synced"
  },
  "legs": [
    {
      "id": 1,
      "legType": "open",
      "side": "buy",
      "quantity": 100,
      "avgPrice": 182.10,
      "startedAt": "...",
      "fillCount": 1
    }
  ],
  "evaluations": {
    "campaign": {
      "overallLabel": "mixed",
      "items": [
        {
          "dimensionKey": "regime_fit",
          "severity": "medium",
          "title": "Regime mismatch",
          "message": "...",
          "visuals": {}
        }
      ]
    },
    "legs": {
      "1": {
        "overallLabel": "aligned",
        "items": [
          {
            "dimensionKey": "entry_timing",
            "severity": "low",
            "title": "Good entry",
            "message": "...",
            "visuals": {}
          }
        ]
      }
    }
  },
  "contexts": [
    {
      "id": 1,
      "legId": 1,
      "contextType": "entry",
      "strategyTags": ["pullback"],
      "hypothesis": "Support at 180 holds",
      "feelingsThen": {"chips": ["calm"]},
      "notes": null
    }
  ]
}
```

---

## 10) What to Build First (Highest Leverage)
1. Schema evolution + ORM models (this plan — Phase A)
2. Campaign builder service from fills
3. Campaign detail UI with timeline anchors
4. Context capture widget (chips + hypothesis)
5. Evaluation cards per decision point with dimension grouping
6. Minimal visuals: price snapshot + risk path

---

## Implementation Notes

### Codebase Conventions
- **Primary keys**: `BigInteger` autoincrement for trade/content tables, `Integer` for user/config tables
- **Financial fields**: `Float` (not `Numeric`)
- **Timestamps**: `DateTime(timezone=True)` with `default=datetime.utcnow`
- **Flexible metadata**: `JSONB` (not JSON)
- **Enum values**: Lowercase strings in CHECK constraints (`'buy'/'sell'`, `'long'/'short'`)
- **Alembic migrations**: Numbered sequentially (001, 002, ...), revision IDs match number prefix
- **ORM style**: SQLAlchemy 2.0 `Mapped[T]` / `mapped_column()` with `Base` from `src/data/database/models.py`

### Key Design Decisions
- **No `trade_idea` table**: `trade_intents` already stores structured pre-execution proposals. Behavioral metadata (hypothesis, strategy_tags) added directly. Emotion/feeling data goes in `decision_contexts` with `context_type='idea'`.
- **No `evaluation_bundle` table**: `trade_evaluations` evolved for multi-scope with `eval_scope` column. Partial unique indexes prevent duplicate evaluations per scope target.
- **No `evaluation_dimension` table**: `trade_evaluation_items` gains `dimension_key` for UI grouping and `visuals` for chart render instructions. This avoids a redundant abstraction layer.
- **`round_trips` → `position_campaigns`**: The table is empty (migration 008 just created it). Clean rename with added columns for multi-leg support.
