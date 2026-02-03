# Trading Buddy Platform — Sitemap + React/Vite Implementation Plan

This document contains:

1. **Complete website sitemap** (public site + auth/onboarding + app portal)
2. **React Router route mapping** (within existing React + Vite frontend)
3. **API contract** (based on existing FastAPI endpoints + new endpoints needed)
4. **Complete TypeScript types** for all API responses
5. **Mock data strategy** for UI-first development
6. **Step-by-step implementation plan** that lets you build the portal UI in parallel with backend work

---

## Current State & Architecture Decision

The existing codebase is **React 18 + Vite + TypeScript** with a **FastAPI** backend. The portal will be built within this stack:

- **Frontend**: React + Vite + react-router (new addition for multi-page routing)
- **Backend**: FastAPI (existing, serves REST API)
- **No SSR needed** — this is a protected dashboard app behind auth
- **Single server runtime** — FastAPI is the sole backend

The existing frontend (`ui/frontend/`) currently serves a regime visualization tool. The trading buddy portal will be built alongside it, sharing the same Vite build and component infrastructure.

---

## 1) Complete Website Sitemap (Evaluation-First)

### 1.1 Public / Marketing (Trust & Positioning)
```
/
├── Home
├── How It Works
├── What We Evaluate
├── What We Don't Do
├── Pricing
├── FAQ
├── About
└── Legal
    ├── Disclaimer
    ├── Terms of Service
    └── Privacy Policy
```

### 1.2 Authentication (Hardcoded for now)
```
/auth
├── Sign Up    (placeholder — hardcoded user)
├── Log In     (placeholder — auto-login to hardcoded user)
└── Forgot Password (placeholder)
```

> **Note:** Auth is not implemented. A hardcoded mock user is used throughout development. See Section 5 (Mock Data Strategy) for details.

### 1.3 Onboarding
```
/onboarding
├── Welcome
├── Trading Profile
├── Risk Preferences
├── Strategy Declaration
└── Broker Consent
```

### 1.4 Core App (Evaluation-Centered)
```
/app
├── Overview
├── Trades
│   ├── All Trades (filterable by: source, flagged status, symbol)
│   └── Source attribute: synced | manual | csv
├── Evaluate Trade (New/Proposed)
├── Trade Analysis (Trade Detail)
│   └── Explore Evaluation Dimensions
│       ├── Regime Fit
│       ├── Entry Timing
│       ├── Exit Logic
│       ├── Risk & Positioning
│       ├── Behavioral Signals (rushed/revenge/etc.)
│       └── Strategy Consistency
├── Insights (single page with tabbed sections)
│   ├── Regime Insights
│   ├── Timing Insights
│   ├── Behavioral Insights
│   ├── Risk Patterns
│   └── Strategy Drift
├── Journal
│   ├── Daily Reflections
│   ├── Trade Notes
│   └── Behavioral Tags
└── Settings
    ├── Trading Profile
    ├── Risk Preferences
    ├── Strategy Definitions
    ├── Broker Integrations
    ├── Evaluation Controls
    └── Data & Privacy
```

### 1.5 Help
```
/help
├── Understanding Evaluations
├── Interpreting Behavioral Signals
├── Why We Flag Trades
├── Common Misunderstandings
└── Contact Support
```

---

## 2) React Router Route Mapping

All routes use `react-router-dom` v6+ with nested layouts.

### 2.1 Route Structure

```
src/
  routes/
    index.tsx               # Route definitions (createBrowserRouter)

  layouts/
    PublicLayout.tsx         # Header + footer for marketing pages
    AppLayout.tsx            # Sidebar + topbar for /app/* pages
    OnboardingLayout.tsx     # Minimal chrome for onboarding flow

  pages/
    # Public
    Home.tsx                 # /
    HowItWorks.tsx           # /how-it-works
    WhatWeEvaluate.tsx       # /what-we-evaluate
    WhatWeDontDo.tsx         # /what-we-dont-do
    Pricing.tsx              # /pricing
    FAQ.tsx                  # /faq
    About.tsx                # /about
    legal/
      Disclaimer.tsx         # /legal/disclaimer
      Terms.tsx              # /legal/terms
      Privacy.tsx            # /legal/privacy

    # Auth (placeholder)
    auth/
      Login.tsx              # /auth/login
      Signup.tsx             # /auth/signup
      ForgotPassword.tsx     # /auth/forgot-password

    # Onboarding
    onboarding/
      Welcome.tsx            # /onboarding/welcome
      Profile.tsx            # /onboarding/profile
      Risk.tsx               # /onboarding/risk
      Strategy.tsx           # /onboarding/strategy
      BrokerConsent.tsx      # /onboarding/broker-consent

    # App Portal (protected)
    app/
      Overview.tsx           # /app
      Trades.tsx             # /app/trades
      TradeDetail.tsx        # /app/trades/:tradeId
      Evaluate.tsx           # /app/evaluate
      Insights.tsx           # /app/insights
      Journal.tsx            # /app/journal
      settings/
        Profile.tsx          # /app/settings/profile
        Risk.tsx             # /app/settings/risk
        Strategies.tsx       # /app/settings/strategies
        Brokers.tsx          # /app/settings/brokers
        EvaluationControls.tsx  # /app/settings/evaluation-controls
        DataPrivacy.tsx      # /app/settings/data-privacy

    # Help
    help/
      Index.tsx              # /help
      Evaluations.tsx        # /help/evaluations
      BehavioralSignals.tsx  # /help/behavioral-signals
      WhyFlags.tsx           # /help/why-flags
      CommonMisunderstandings.tsx  # /help/common-misunderstandings
      Contact.tsx            # /help/contact
```

### 2.2 Router Configuration

```typescript
// src/routes/index.tsx
import { createBrowserRouter } from 'react-router-dom';

export const router = createBrowserRouter([
  // Public pages
  {
    element: <PublicLayout />,
    children: [
      { path: '/', element: <Home /> },
      { path: '/how-it-works', element: <HowItWorks /> },
      { path: '/what-we-evaluate', element: <WhatWeEvaluate /> },
      { path: '/what-we-dont-do', element: <WhatWeDontDo /> },
      { path: '/pricing', element: <Pricing /> },
      { path: '/faq', element: <FAQ /> },
      { path: '/about', element: <About /> },
      { path: '/legal/disclaimer', element: <Disclaimer /> },
      { path: '/legal/terms', element: <Terms /> },
      { path: '/legal/privacy', element: <Privacy /> },
    ],
  },

  // Auth (placeholder)
  {
    path: '/auth',
    children: [
      { path: 'login', element: <Login /> },
      { path: 'signup', element: <Signup /> },
      { path: 'forgot-password', element: <ForgotPassword /> },
    ],
  },

  // Onboarding
  {
    path: '/onboarding',
    element: <OnboardingLayout />,
    children: [
      { path: 'welcome', element: <Welcome /> },
      { path: 'profile', element: <OnboardingProfile /> },
      { path: 'risk', element: <OnboardingRisk /> },
      { path: 'strategy', element: <OnboardingStrategy /> },
      { path: 'broker-consent', element: <BrokerConsent /> },
    ],
  },

  // App portal (protected — uses hardcoded user for now)
  {
    path: '/app',
    element: <AppLayout />,
    children: [
      { index: true, element: <Overview /> },
      { path: 'trades', element: <Trades /> },
      { path: 'trades/:tradeId', element: <TradeDetail /> },
      { path: 'evaluate', element: <Evaluate /> },
      { path: 'insights', element: <Insights /> },
      { path: 'journal', element: <Journal /> },
      { path: 'settings/profile', element: <SettingsProfile /> },
      { path: 'settings/risk', element: <SettingsRisk /> },
      { path: 'settings/strategies', element: <SettingsStrategies /> },
      { path: 'settings/brokers', element: <SettingsBrokers /> },
      { path: 'settings/evaluation-controls', element: <SettingsEvaluationControls /> },
      { path: 'settings/data-privacy', element: <SettingsDataPrivacy /> },
    ],
  },

  // Help
  {
    path: '/help',
    element: <PublicLayout />,
    children: [
      { index: true, element: <HelpIndex /> },
      { path: 'evaluations', element: <HelpEvaluations /> },
      { path: 'behavioral-signals', element: <HelpBehavioralSignals /> },
      { path: 'why-flags', element: <HelpWhyFlags /> },
      { path: 'common-misunderstandings', element: <HelpCommonMisunderstandings /> },
      { path: 'contact', element: <HelpContact /> },
    ],
  },
]);
```

### 2.3 Navigation Config

```typescript
// src/lib/nav.ts
export const appNavSections = [
  {
    label: 'Overview',
    path: '/app',
    icon: 'LayoutDashboard',
  },
  {
    label: 'Trades',
    path: '/app/trades',
    icon: 'ArrowRightLeft',
  },
  {
    label: 'Evaluate',
    path: '/app/evaluate',
    icon: 'ClipboardCheck',
  },
  {
    label: 'Insights',
    path: '/app/insights',
    icon: 'TrendingUp',
  },
  {
    label: 'Journal',
    path: '/app/journal',
    icon: 'BookOpen',
  },
  {
    label: 'Settings',
    path: '/app/settings/profile',
    icon: 'Settings',
    children: [
      { label: 'Profile', path: '/app/settings/profile' },
      { label: 'Risk', path: '/app/settings/risk' },
      { label: 'Strategies', path: '/app/settings/strategies' },
      { label: 'Brokers', path: '/app/settings/brokers' },
      { label: 'Evaluation Controls', path: '/app/settings/evaluation-controls' },
      { label: 'Data & Privacy', path: '/app/settings/data-privacy' },
    ],
  },
];
```

---

## 3) API Contract

All endpoints are served by FastAPI at `http://localhost:8000`. The contract is split into **existing endpoints** (already implemented) and **new endpoints** (to be built).

### 3.1 Existing Endpoints (Already Implemented)

#### Trading Buddy — Trade Evaluation

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/trading-buddy/intents` | Create a new trade intent (draft) |
| `POST` | `/api/trading-buddy/evaluate` | Evaluate a trade intent against all evaluators |
| `GET`  | `/api/trading-buddy/evaluators` | List all available evaluators |
| `GET`  | `/api/trading-buddy/health` | Health check |

#### Broker Integration

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/broker/connect` | Initiate broker connection via SnapTrade |
| `POST` | `/api/broker/sync` | Sync trades/accounts from connected brokers |
| `GET`  | `/api/broker/trades` | Get trade history |
| `GET`  | `/api/broker/status` | Check connected brokerages |
| `GET`  | `/api/broker/callback` | Handle SnapTrade callback |

#### Market Data & Analysis

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/tickers` | List all tickers |
| `GET`  | `/api/tickers/{symbol}/summary` | Ticker data summary |
| `GET`  | `/api/ohlcv/{symbol}` | OHLCV price data |
| `GET`  | `/api/features/{symbol}` | Computed features |
| `GET`  | `/api/statistics/{symbol}` | Statistics summary |
| `GET`  | `/api/regimes/{symbol}` | HMM regime states |
| `GET`  | `/api/pca/regimes/{symbol}` | PCA regime states |
| `POST` | `/api/analyze/{symbol}` | Full HMM analysis pipeline |
| `POST` | `/api/pca/analyze/{symbol}` | PCA + K-means analysis |
| `POST` | `/api/compute-features/{symbol}` | Compute features for all timeframes |
| `GET`  | `/api/sync-status/{symbol}` | Data sync status |
| `POST` | `/api/sync/{symbol}` | Trigger data sync |
| `POST` | `/api/import` | Import data from file |
| `GET`  | `/api/health` | System health check |
| `DELETE` | `/api/cache` | Clear data cache |

### 3.2 New Endpoints (To Be Built)

These are required for the portal but do not yet exist in the backend.

#### User / Auth (Hardcoded for now)

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/me` | Get current user profile |
| `PUT`  | `/api/me/profile` | Update trading profile |
| `PUT`  | `/api/me/risk-preferences` | Update risk preferences |

#### Trades (Extended)

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/trading-buddy/trades` | List trades with filters (extends broker/trades) |
| `GET`  | `/api/trading-buddy/trades/{tradeId}` | Get single trade with evaluation |
| `POST` | `/api/trading-buddy/trades` | Create manual trade entry |

**Query parameters for `GET /api/trading-buddy/trades`:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | all | Filter: `synced`, `manual`, `csv`, `proposed` |
| `flagged` | boolean | — | Filter by flagged status |
| `symbol` | string | — | Filter by symbol |
| `status` | string | all | Filter: `open`, `closed`, `proposed` |
| `sort` | string | `-entry_time` | Sort field (prefix `-` for desc) |
| `page` | int | 1 | Page number |
| `limit` | int | 20 | Items per page |

#### Insights (Aggregated)

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/trading-buddy/insights/summary` | Overview stats (win rate, avg R:R, etc.) |
| `GET`  | `/api/trading-buddy/insights/regimes` | Regime-based performance breakdown |
| `GET`  | `/api/trading-buddy/insights/timing` | Entry/exit timing patterns |
| `GET`  | `/api/trading-buddy/insights/behavioral` | Behavioral pattern counts |
| `GET`  | `/api/trading-buddy/insights/risk` | Risk metric trends |
| `GET`  | `/api/trading-buddy/insights/strategy-drift` | Strategy consistency over time |

#### Journal

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/trading-buddy/journal` | List journal entries |
| `POST` | `/api/trading-buddy/journal` | Create journal entry |
| `PUT`  | `/api/trading-buddy/journal/{entryId}` | Update journal entry |
| `GET`  | `/api/trading-buddy/journal/tags` | List all behavioral tags |

#### Settings (Extended)

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/trading-buddy/strategies` | List user strategy definitions |
| `POST` | `/api/trading-buddy/strategies` | Create strategy definition |
| `PUT`  | `/api/trading-buddy/strategies/{id}` | Update strategy definition |
| `GET`  | `/api/trading-buddy/evaluation-controls` | Get evaluation toggle settings |
| `PUT`  | `/api/trading-buddy/evaluation-controls` | Update evaluation toggles |

#### Onboarding

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/trading-buddy/onboarding/status` | Get onboarding progress |
| `POST` | `/api/trading-buddy/onboarding/profile` | Submit trading profile |
| `POST` | `/api/trading-buddy/onboarding/risk` | Submit risk preferences |
| `POST` | `/api/trading-buddy/onboarding/strategy` | Submit strategy declaration |
| `POST` | `/api/trading-buddy/onboarding/complete` | Mark onboarding done |

---

## 4) TypeScript Types

These types mirror the existing Pydantic models on the backend and add new types for portal-specific features. Types for already-existing endpoints are documented in `ui/frontend/src/types.ts` and `ui/frontend/src/api.ts`.

### 4.1 User & Auth

```typescript
// Hardcoded during development — no real auth
interface User {
  id: number;
  email: string;
  name: string;
  onboarding_complete: boolean;
  created_at: string;
}

interface TradingProfile {
  experience_level: 'beginner' | 'intermediate' | 'advanced';
  trading_style: 'day_trading' | 'swing' | 'scalping' | 'position';
  primary_markets: string[];       // e.g. ['US_EQUITIES', 'OPTIONS']
  typical_timeframes: string[];    // e.g. ['1Min', '5Min', '1Hour']
  account_size_range: string;      // e.g. '$10k-$50k'
}

interface RiskPreferences {
  max_loss_per_trade_pct: number;  // e.g. 2.0
  max_daily_loss_pct: number;      // e.g. 5.0
  max_open_positions: number;
  risk_reward_minimum: number;     // e.g. 1.5
  stop_loss_required: boolean;
}
```

### 4.2 Trades (Extended)

```typescript
// Extends the existing Trade type from api.ts
interface TradeSummary {
  id: string;
  symbol: string;
  direction: 'long' | 'short';
  entry_price: number;
  exit_price: number | null;
  quantity: number;
  entry_time: string;
  exit_time: string | null;
  source: 'synced' | 'manual' | 'csv' | 'proposed';
  brokerage: string | null;
  is_flagged: boolean;
  flag_count: number;
  status: 'open' | 'closed' | 'proposed';
  timeframe: string;
}

interface TradeListResponse {
  trades: TradeSummary[];
  total: number;
  page: number;
  limit: number;
}

interface TradeDetail extends TradeSummary {
  stop_loss: number | null;
  profit_target: number | null;
  risk_reward_ratio: number | null;
  pnl: number | null;
  pnl_pct: number | null;
  evaluation: EvaluationResponse | null;  // reuses existing type
  notes: string | null;
  tags: string[];
}
```

### 4.3 Evaluation (Already Exists — Documented Here for Reference)

These types already exist as Pydantic models in `src/api/trading_buddy.py`:

```typescript
// Maps to TradeIntentCreate (Python)
interface TradeIntentCreate {
  symbol: string;
  direction: 'long' | 'short';
  timeframe: string;
  entry_price: number;
  stop_loss: number;
  profit_target: number;
  position_size?: number;
  position_value?: number;
  rationale?: string;
}

// Maps to TradeIntentResponse (Python)
interface TradeIntentResponse {
  intent_id: number | null;
  symbol: string;
  direction: string;
  timeframe: string;
  entry_price: number;
  stop_loss: number;
  profit_target: number;
  position_size: number | null;
  position_value: number | null;
  rationale: string | null;
  status: string;
  risk_reward_ratio: number;
  total_risk: number | null;
  created_at: string;
}

// Maps to EvaluationResponse (Python)
interface EvaluationResponse {
  score: number;
  summary: string;
  has_blockers: boolean;
  top_issues: EvaluationItemResponse[];
  all_items: EvaluationItemResponse[];
  counts: Record<string, number>;      // { info: 2, warning: 1, blocker: 0 }
  evaluators_run: string[];
  evaluated_at: string;
}

interface EvaluationItemResponse {
  evaluator: string;
  code: string;
  severity: 'info' | 'warning' | 'critical' | 'blocker';
  title: string;
  message: string;
  evidence: EvidenceResponse[];
}

interface EvidenceResponse {
  metric_name: string;
  value: number;
  threshold: number | null;
  comparison: '<' | '<=' | '>' | '>=' | '==' | '!=' | null;
  unit: string | null;
}

// Maps to EvaluateRequest (Python)
interface EvaluateRequest {
  intent: TradeIntentCreate;
  evaluators?: string[];
  include_context: boolean;
}

// Maps to EvaluateResponse (Python)
interface EvaluateResponse {
  intent: TradeIntentResponse;
  evaluation: EvaluationResponse;
  context_summary: Record<string, unknown> | null;
}
```

### 4.4 Insights

```typescript
interface InsightsSummary {
  total_trades: number;
  total_evaluated: number;
  flagged_count: number;
  blocker_count: number;
  avg_score: number;
  avg_risk_reward: number;
  win_rate: number | null;           // null if not enough closed trades
  most_common_flag: string | null;
  period: { start: string; end: string };
}

interface RegimeInsight {
  regime_label: string;
  trade_count: number;
  avg_score: number;
  flagged_pct: number;
  avg_pnl_pct: number | null;
}

interface TimingInsight {
  hour_of_day: number;
  trade_count: number;
  avg_score: number;
  flagged_pct: number;
}

interface BehavioralInsight {
  signal: string;                    // e.g. 'rushed_entry', 'revenge_trade'
  occurrence_count: number;
  pct_of_trades: number;
  avg_outcome_pct: number | null;
}

interface RiskInsight {
  date: string;
  avg_risk_reward: number;
  trades_without_stop: number;
  max_position_pct: number;
}

interface StrategyDriftInsight {
  date: string;
  consistency_score: number;         // 0-100
  deviations: string[];              // e.g. ['timeframe_mismatch', 'oversized_position']
}
```

### 4.5 Journal

```typescript
interface JournalEntry {
  id: string;
  date: string;
  type: 'daily_reflection' | 'trade_note';
  content: string;
  trade_id: string | null;          // linked trade if type=trade_note
  tags: string[];                   // behavioral tags
  mood: 'confident' | 'neutral' | 'anxious' | 'frustrated' | null;
  created_at: string;
  updated_at: string;
}

interface JournalEntryCreate {
  date: string;
  type: 'daily_reflection' | 'trade_note';
  content: string;
  trade_id?: string;
  tags?: string[];
  mood?: 'confident' | 'neutral' | 'anxious' | 'frustrated';
}

interface BehavioralTag {
  name: string;
  category: 'emotional' | 'process' | 'risk' | 'timing';
  description: string;
}
```

### 4.6 Settings / Strategies

```typescript
interface StrategyDefinition {
  id: string;
  name: string;
  description: string;
  direction: 'long' | 'short' | 'both';
  timeframes: string[];
  entry_criteria: string;
  exit_criteria: string;
  max_risk_pct: number;
  min_risk_reward: number;
  is_active: boolean;
}

interface EvaluationControls {
  evaluators_enabled: Record<string, boolean>;  // evaluator name → on/off
  auto_evaluate_synced: boolean;
  notification_on_blocker: boolean;
  severity_threshold: 'info' | 'warning' | 'critical' | 'blocker';
}
```

### 4.7 Onboarding

```typescript
interface OnboardingStatus {
  profile_complete: boolean;
  risk_complete: boolean;
  strategy_complete: boolean;
  broker_connected: boolean;
  all_complete: boolean;
}
```

### 4.8 Broker (Already Exists — Documented Here for Reference)

```typescript
// These already exist in ui/frontend/src/api.ts
interface ConnectResponse {
  redirect_url: string;
}

interface SyncResponse {
  status: string;
  trades_synced: number;
}

interface BrokerStatus {
  connected: boolean;
  brokerages: string[];
}
```

---

## 5) Mock Data Strategy

The portal UI is built against mock data while the backend is developed in parallel. The mock layer mirrors the real API client interface so switching to real APIs is a one-line change.

### 5.1 Architecture

```
ui/frontend/src/
  mocks/
    enable.ts              # Toggle: USE_MOCKS = true | false
    mockUser.ts            # Hardcoded user + auth context
    fixtures/
      trades.ts            # 12-15 sample trades
      evaluations.ts       # 3-4 full evaluation bundles
      insights.ts          # Aggregated insight data
      journal.ts           # Sample journal entries
      strategies.ts        # Sample strategy definitions
      tags.ts              # Behavioral tag list
      onboarding.ts        # Onboarding state
    mockApi.ts             # Mock implementation of every API function
  api/
    client.ts              # The actual API client (axios-based, existing)
    index.ts               # Re-exports: returns mock or real client based on toggle
```

### 5.2 Mock Toggle

```typescript
// src/mocks/enable.ts
export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false';
// Default: mocks ON. Set VITE_USE_MOCKS=false in .env to use real backend.
```

```typescript
// src/api/index.ts
import { USE_MOCKS } from '../mocks/enable';
import * as realApi from './client';
import * as mockApi from '../mocks/mockApi';

const api = USE_MOCKS ? mockApi : realApi;
export default api;
```

All page components import from `src/api/index.ts` — never from `client.ts` or `mockApi.ts` directly. When the backend is ready, set `VITE_USE_MOCKS=false` and the entire UI switches to real API calls.

### 5.3 Hardcoded Mock User

```typescript
// src/mocks/mockUser.ts
import type { User, TradingProfile, RiskPreferences } from '../types';

export const MOCK_USER: User = {
  id: 1,
  email: 'trader@example.com',
  name: 'Demo Trader',
  onboarding_complete: true,
  created_at: '2025-01-15T10:00:00Z',
};

export const MOCK_PROFILE: TradingProfile = {
  experience_level: 'intermediate',
  trading_style: 'day_trading',
  primary_markets: ['US_EQUITIES'],
  typical_timeframes: ['1Min', '5Min', '1Hour'],
  account_size_range: '$10k-$50k',
};

export const MOCK_RISK_PREFERENCES: RiskPreferences = {
  max_loss_per_trade_pct: 2.0,
  max_daily_loss_pct: 5.0,
  max_open_positions: 5,
  risk_reward_minimum: 1.5,
  stop_loss_required: true,
};
```

Route guards during mock mode:
- `/app/*` routes check `MOCK_USER` exists (always true) — no redirect
- `/auth/login` auto-navigates to `/app`
- Onboarding pages read `MOCK_USER.onboarding_complete` to decide skip vs show

### 5.4 Mock Trade Fixtures

The fixtures should cover these scenarios:

| # | Symbol | Direction | Source | Status | Flagged | Evaluation |
|---|--------|-----------|--------|--------|---------|------------|
| 1 | AAPL | long | synced | closed | yes | blocker: rushed entry during unfavorable regime |
| 2 | AAPL | long | synced | closed | no | clean: all dimensions ok |
| 3 | TSLA | short | manual | closed | yes | warning: oversized position, no stop |
| 4 | SPY | long | synced | open | no | info: regime is neutral |
| 5 | NVDA | long | proposed | proposed | yes | blocker: revenge trade pattern |
| 6 | META | short | manual | closed | yes | critical: against declared strategy |
| 7 | MSFT | long | synced | closed | no | clean |
| 8 | AMD | long | csv | closed | yes | warning: poor entry timing |
| 9 | GOOG | short | synced | closed | no | info: exit could be tighter |
| 10 | AMZN | long | manual | open | no | not yet evaluated |
| 11 | QQQ | long | proposed | proposed | yes | blocker: extreme volatility regime |
| 12 | JPM | long | synced | closed | no | clean |

Each fixture includes realistic prices, timestamps, and at least one full `EvaluationResponse` with populated `evidence` arrays.

### 5.5 Mock API Implementation Pattern

```typescript
// src/mocks/mockApi.ts
import { MOCK_TRADES } from './fixtures/trades';
import { MOCK_EVALUATIONS } from './fixtures/evaluations';
import type { TradeListResponse, TradeDetail } from '../types';

// Simulate network delay
const delay = (ms = 200) => new Promise(r => setTimeout(r, ms));

export async function fetchTrades(params: {
  source?: string;
  flagged?: boolean;
  symbol?: string;
  page?: number;
  limit?: number;
}): Promise<TradeListResponse> {
  await delay();
  let filtered = [...MOCK_TRADES];
  if (params.source) filtered = filtered.filter(t => t.source === params.source);
  if (params.flagged !== undefined) filtered = filtered.filter(t => t.is_flagged === params.flagged);
  if (params.symbol) filtered = filtered.filter(t => t.symbol.includes(params.symbol!.toUpperCase()));

  const page = params.page ?? 1;
  const limit = params.limit ?? 20;
  const start = (page - 1) * limit;

  return {
    trades: filtered.slice(start, start + limit),
    total: filtered.length,
    page,
    limit,
  };
}

export async function fetchTradeDetail(tradeId: string): Promise<TradeDetail> {
  await delay();
  const trade = MOCK_TRADES.find(t => t.id === tradeId);
  if (!trade) throw new Error(`Trade ${tradeId} not found`);
  const evaluation = MOCK_EVALUATIONS[tradeId] ?? null;
  return { ...trade, evaluation, notes: null, tags: [] };
}

// ... same pattern for all other API functions
```

---

## 6) Implementation Steps

The portal is built incrementally. Each step produces a working UI backed by mock data.

### Step 1 — Install Dependencies & Setup Routing

Add to existing `ui/frontend/`:
- `react-router-dom` for routing
- `tailwindcss` for styling (or keep existing CSS approach — decide before starting)

Create the route config (`src/routes/index.tsx`), the three layouts (`PublicLayout`, `AppLayout`, `OnboardingLayout`), and the navigation config (`src/lib/nav.ts`).

Wire up `main.tsx` to use `RouterProvider`.

### Step 2 — Create Mock Layer

Build the mock infrastructure:
- `src/mocks/enable.ts` — toggle
- `src/mocks/mockUser.ts` — hardcoded user
- `src/mocks/fixtures/trades.ts` — 12 trade fixtures with all fields
- `src/mocks/fixtures/evaluations.ts` — 3-4 full evaluation response objects
- `src/mocks/mockApi.ts` — mock implementations for all API functions
- `src/api/index.ts` — the toggle export

### Step 3 — Build AppLayout (Portal Shell)

The shell all `/app/*` pages share:
- **Sidebar**: nav sections from `lib/nav.ts`, active state, collapsible
- **Top bar**: user name (hardcoded), search (placeholder), notifications (placeholder)
- **Main content area**: `<Outlet />` from react-router

### Step 4 — Build Trades List Page

Route: `/app/trades`

- Table of trades from `api.fetchTrades()`
- Filter controls: source dropdown, flagged toggle, symbol search
- Sort by date (default), flagged status
- Click row → navigate to `/app/trades/:tradeId`
- Pagination

### Step 5 — Build Trade Analysis Page (Core Page)

Route: `/app/trades/:tradeId`

Fetch `api.fetchTradeDetail(tradeId)` and render:
- **Header**: symbol, direction, entry/exit, timeframe, source badge
- **Flag summary**: count of issues by severity
- **Dimension explorer**: tabs or accordion for each evaluation dimension
  - Regime Fit
  - Entry Timing
  - Exit Logic
  - Risk & Positioning
  - Behavioral Signals
  - Strategy Consistency
- **Evidence panel**: per-dimension "Why flagged?" with metric values and thresholds
- **Visual references**: max 1-2 charts per dimension, only when meaningful

### Step 6 — Build Evaluate Trade Flow

Route: `/app/evaluate`

1. Form: symbol, direction, timeframe, entry price, stop loss, profit target, position size, rationale
2. Submit → `api.evaluateTrade(intent)` (maps to `POST /api/trading-buddy/evaluate`)
3. Show result inline using the same Trade Analysis component from Step 5
4. Optionally: save as proposed trade and navigate to `/app/trades/:tradeId`

**Important**: The evaluate flow and the trade detail page share the same evaluation display components.

### Step 7 — Build Overview Page

Route: `/app`

Dashboard with summary cards:
- Recent trades (last 5)
- Active flags count
- Quick evaluate CTA
- Broker connection status
- Journal streak (if applicable)

### Step 8 — Build Insights Page

Route: `/app/insights`

Single page with tab sections:
- **Summary** tab: key stats (total trades, flagged %, avg score)
- **Regimes** tab: performance by regime
- **Timing** tab: entry timing patterns
- **Behavioral** tab: behavioral signal counts
- **Risk** tab: risk metric trends
- **Strategy Drift** tab: consistency over time

Start simple: one summary card or chart per tab. Link back to example trades.

### Step 9 — Build Journal Page

Route: `/app/journal`

- List of journal entries, sorted by date
- Create entry form: type (daily reflection / trade note), content, tags, mood
- Link trade notes to specific trades
- Filter by type, tag

### Step 10 — Build Settings Pages

Routes: `/app/settings/*`

- **Profile**: display/edit trading profile
- **Risk**: display/edit risk preferences
- **Strategies**: CRUD for strategy definitions
- **Brokers**: connect broker CTA, list connected brokerages, sync status (reuses existing `BrokerConnect` component)
- **Evaluation Controls**: toggle evaluators on/off, severity threshold
- **Data & Privacy**: data export, account info (placeholder)

### Step 11 — Build Public Pages & Help (Lower Priority)

Marketing pages and help content. Static content, no API calls. Build last.

### Step 12 — Switch to Real Backend

When backend endpoints are ready:
1. Set `VITE_USE_MOCKS=false` in `.env`
2. Ensure `src/api/client.ts` implements same function signatures as `mockApi.ts`
3. Validate responses match TypeScript types (add Zod validation if drift is a concern)
4. Remove mock fixtures (or keep for testing)

---

## 7) Tech Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| **Framework** | React 18 + Vite | Existing stack |
| **Language** | TypeScript 5.x | Existing |
| **Routing** | react-router-dom v6 | New — file-based routing not needed |
| **Styling** | TailwindCSS | New — or keep custom CSS (decide before Step 1) |
| **Component library** | shadcn/ui (optional) | Owned components, not a dependency |
| **HTTP client** | Axios | Existing |
| **Server state** | TanStack Query (optional) | Adds caching, refetch, loading states |
| **UI state** | React context + useState | Start simple; add Zustand only if needed |
| **Charts** | Plotly.js / lightweight-charts | Existing |
| **Mock layer** | `mockApi.ts` + fixture files | Simple, no extra dependencies |
| **Backend** | FastAPI | Existing |
| **Validation** | Zod (optional) | Add when switching from mocks to real API |

---

## 8) Design Constraints

- Keep **one primary task per page**
- Show **summary first, details on expand**
- Visuals only to support an evaluation point — not decoration
- Limit concurrent charts (max 2 visible at once)
- No flashy scores or gamification — the assistant is a mentor, not a scorekeeper
- Flags should explain **why** in plain language, not just show red/green
- Every flagged dimension must link to evidence (metric name, value, threshold)

---

## 9) Future Docs (To Be Added as Needed)

- `EVALUATION_SCHEMA.md` — JSON schema for trade evaluations
- `TRADE_ANALYSIS_UI.md` — wireframe + component breakdown for the trade detail page
- `BROKER_INTEGRATIONS.md` — connector strategy + permissions UX
