# Trading Buddy Platform - Detailed Implementation TODOs

Based on the [Master Roadmap](./Trading_Buddy_Master_Roadmap_and_DB_Schema.md) and current codebase analysis.

**Last reviewed**: 2026-02-03

---

## Validation: Integration with Existing Codebase

The following existing infrastructure will be **reused** (no need to rebuild):

| Existing Component | Location | Reuse in Trading Buddy |
|---|---|---|
| **Ticker Management** | `src/data/database/models.py::Ticker` | Used by `ContextPackBuilder` to resolve symbols |
| **OHLCV Bars** | `src/data/database/models.py::OHLCVBar` | Primary market data source for all evaluators |
| **Computed Features (TA)** | `src/data/database/models.py::ComputedFeature` | TA features + HMM states already stored here |
| **OHLCVRepository** | `src/data/database/market_repository.py` | Data access layer for bars, features, states |
| **Feature Pipeline** | `src/features/pipeline.py::FeaturePipeline` | Compute TA features on-the-fly if needed |
| **HMM Inference** | `src/features/state/hmm/inference.py::InferenceEngine` | State vectors, regime probabilities, OOD detection |
| **Multi-TF Inference** | `src/features/state/hmm/inference.py::MultiTimeframeInferenceEngine` | HTF state carry-forward with TTL |
| **Existing API** | `ui/backend/api.py` | Main FastAPI app; Trading Buddy routes are in `src/api/trading_buddy.py` |
| **Broker Integration** | `src/api/broker.py` | SnapTrade broker connection, trade history sync |
| **Trading Buddy Repository** | `src/data/database/trading_repository.py` | CRUD for accounts, rules, intents, evaluations |

### Key Integration Notes

1. **ContextPackBuilder** (`src/evaluators/context.py`) already uses:
   - `OHLCVRepository.get_bars()` for latest OHLCV ✅
   - `OHLCVRepository.get_features()` for TA indicators ✅
   - `OHLCVRepository.get_states()` for HMM regime data ✅
   - Multi-timeframe loading via `additional_timeframes` parameter ✅
   - In-memory caching with 60-second TTL ✅
   - **Not yet integrated**: `InferenceEngine` for live regime inference (currently reads stored states only)
   - **Not yet integrated**: `MultiTimeframeInferenceEngine` for MTFA alignment scoring

2. **Database additions** are in Alembic migration `005_trading_buddy_tables.py` ✅ and `006_broker_integration_tables.py` ✅.

3. **Key Levels** computation exists inline in `ContextPackBuilder._compute_key_levels()` (basic: prior day HLC, pivots, rolling range). Anchored VWAP and support/resistance detection remain TODO.

4. **API endpoints** are in `src/api/trading_buddy.py` as a FastAPI router mounted at `/api/trading-buddy/`. The broker endpoints are in `src/api/broker.py` mounted at `/api/broker/`.

5. **Frontend portal** pages exist in `ui/frontend/src/portal/pages/` with mock data. The evaluate form, trade detail, journal, insights, and settings pages are scaffolded and ready for backend integration.

---

## Phase 0: Foundations (Core Platform) — ✅ COMPLETE

**Goal**: Establish the core infrastructure, database schema, and evaluation orchestration engine.

**Status**: All core infrastructure is implemented. Database persistence, user config loading, and guardrails are all wired into the API layer.

- [x] **Database Schema Expansion**
  - [x] Alembic migration `005_trading_buddy_tables.py` created and applied.
  - [x] SQLAlchemy models in `src/data/database/trading_buddy_models.py`:
    - [x] `UserAccount` (`user_accounts`)
    - [x] `UserRule` (`user_rules`)
    - [x] `TradeIntent` (`trade_intents`)
    - [x] `TradeEvaluation` (`trade_evaluations`)
    - [x] `TradeEvaluationItem` (`trade_evaluation_items`)

- [x] **Core Domain Objects (`src/trade/`)**
  - [x] `TradeIntent` dataclass in `src/trade/intent.py` with validation, computed properties (R:R, total risk), serialization.
  - [x] `EvaluationResult` dataclass in `src/trade/evaluation.py` with severity filtering, top issues, scoring.
  - [x] `Evidence` dataclass in `src/trade/evaluation.py` with threshold violation detection.
  - [x] `Severity` enum: INFO, WARNING, CRITICAL, BLOCKER with priority mapping.

- [x] **ContextPack Infrastructure (`src/evaluators/context.py`)**
  - [x] `ContextPack` class with bars, features, regimes, key levels per timeframe.
  - [x] `ContextPackBuilder` with in-memory caching (60s TTL).
  - [x] Integrates `OHLCVRepository` for bars, features, and HMM states.
  - [x] `RegimeContext` and `KeyLevels` data containers.

- [x] **Evaluator Engine (`src/evaluators/`)**
  - [x] `base.py`: `Evaluator` abstract base class with `EvaluatorConfig`.
  - [x] `registry.py`: `@register_evaluator` decorator, `get_evaluator()`, `get_all_evaluators()`, `list_evaluators()`.
  - [x] `evidence.py`: `check_threshold()`, `compute_zscore()`, `compare_to_atr()`, `compute_percentile()`, formatting helpers.

- [x] **Orchestrator (`src/orchestrator.py`)**
  - [x] `EvaluatorOrchestrator` with `OrchestratorConfig`.
  - [x] Sequential and parallel (ThreadPoolExecutor) execution.
  - [x] Result deduplication by code (keeps highest severity).
  - [x] Penalty-based scoring (100 base - 40/blocker, 20/critical, 5/warning).
  - [x] Summary generation.

- [x] **API/UI Shell**
  - [x] `POST /api/trading-buddy/intents` — creates draft intent (validation only).
  - [x] `POST /api/trading-buddy/evaluate` — runs full evaluation pipeline, returns score + findings.
  - [x] `GET /api/trading-buddy/evaluators` — lists registered evaluators.
  - [x] `GET /api/trading-buddy/health` — health check.

### Phase 0 Remaining Gaps — ✅ RESOLVED

- [x] **Wire database persistence into API endpoints**
  - [x] `POST /intents` persists via `TradingBuddyRepository.create_trade_intent()` and returns the persisted `intent_id`.
  - [x] `POST /evaluate` persists intent and evaluation via `TradingBuddyRepository.save_evaluation()`, linked by `intent_id`.
  - [x] `GET /api/trading-buddy/intents/{intent_id}` retrieves a persisted intent and its evaluation.

- [x] **Wire user-specific configuration into evaluation pipeline**
  - [x] The evaluate endpoint calls `TradingBuddyRepository.build_evaluator_configs()` with the user's `account_id` and passes configs via `OrchestratorConfig.evaluator_configs`. Accepts optional `account_id` in request (defaults to 1).

---

## Phase 1: Trust + Risk-First MVP — ✅ COMPLETE

**Goal**: Implement the critical safety checks to deliver immediate value.

**Status**: Both core evaluators and guardrails are fully implemented and wired into the live evaluation flow. User-specific rules are loaded and applied at evaluation time.

- [x] **Risk & Reward Evaluator (`src/evaluators/risk_reward.py`)**
  - [x] `RiskRewardEvaluator` with 5 checks:
    - [x] RR001: R:R ratio vs minimum (3-tier severity based on deviation).
    - [x] RR002: Position risk vs account risk limit (`max_risk_per_trade_pct`).
    - [x] RR003: Stop loss too tight (< min ATR multiple).
    - [x] RR004: Stop loss too wide (> max ATR multiple).
    - [x] RR005: Position size too large (% of account).

- [x] **Exit Plan Evaluator (`src/evaluators/exit_plan.py`)**
  - [x] `ExitPlanEvaluator` with 6 checks:
    - [x] EP001: Missing stop loss (BLOCKER).
    - [x] EP002: Missing profit target (CRITICAL).
    - [x] EP003: Stop extremely close to entry.
    - [x] EP004: Target extremely close to entry.
    - [x] EP005: Stop near key level (proximity warning).
    - [x] EP006: Target at key level (positive info).
    - [x] EP000: Exit plan complete (info when all good).

- [x] **Guardrails (`src/rules/guardrails.py`)**
  - [x] `contains_prediction()` — regex detection of predictive language.
  - [x] `sanitize_message()` — replaces predictive phrases.
  - [x] `validate_evaluation_result()` / `sanitize_evaluation_result()`.
  - [x] 15 `WarningTemplate` entries for non-predictive messaging.

- [x] **User Configuration (data layer)**
  - [x] `UserAccount` model with risk defaults (max_position_size_pct, max_risk_per_trade_pct, max_daily_loss_pct, min_risk_reward_ratio).
  - [x] `UserRule` model with per-evaluator parameter overrides (JSONB).
  - [x] `TradingBuddyRepository.build_evaluator_configs()` merges account defaults with rule overrides.

### Phase 1 Remaining Gaps — ✅ RESOLVED

- [x] **Wire guardrails into evaluation pipeline**
  - [x] The `/evaluate` endpoint calls `validate_evaluation_result()` and `sanitize_evaluation_result()` before returning results. Guardrail violations are logged as warnings.

- [x] **Wire user config loading in evaluate endpoint**
  - [x] Resolved as part of Phase 0 gap fix — `build_evaluator_configs()` is called and configs are passed to the orchestrator.

---

## Phase 2: MTFA + Regime + Key Levels — ✅ COMPLETE

**Goal**: Integrate market context (Regime, MTFA, Levels) into the evaluation.

**Status**: Fully implemented. `ContextPackBuilder` enriches regime context with transition risk, entropy, and state labels from HMM model artifacts. VWAP is populated from features. MTFA alignment is computed across timeframes. Two new evaluators and two new API endpoints are live.

### Prerequisites (from Phase 0/1 gaps) — ✅ ALL MET

- [x] Database persistence wired into API endpoints (intent + evaluation storage).
- [x] `build_evaluator_configs()` wired into the evaluate flow with user-specific thresholds.
- [x] Guardrails wired into the evaluation pipeline.

### Implementation

- [x] **Bug Fix: `get_states` wildcard bug**
  - [x] Added `get_latest_states()` to `OHLCVRepository` — retrieves the most recent state row for a symbol/timeframe regardless of `model_id`, fixing the broken `get_states(model_id="%")` pattern.

- [x] **Enrich Key Levels (`src/evaluators/context.py`)**
  - [x] VWAP populated from `vwap_60` feature column when available.
  - [x] VWAP included in `distance_to_nearest_level()` calculation.
  - [ ] Add dynamic support/resistance detection (e.g., swing high/low identification from recent bars) — deferred to Phase 3.

- [x] **Enrich Regime Context in `ContextPackBuilder`**
  - [x] **Transition Risk**: Loaded from HMM model artifacts (`GaussianHMMWrapper.transition_matrix`) — max off-diagonal value for current state.
  - [x] **Entropy**: Approximate entropy computed from `state_prob` using max-entropy distribution formula.
  - [x] **State Label**: Mapped from `ModelMetadata.state_mapping` when available, falls back to generic `state_N` label.
  - [x] Graceful degradation when model artifacts don't exist on disk.

- [x] **MTFA Alignment in `ContextPack`**
  - [x] Added `MTFAContext` dataclass with `alignment_score`, `conflicts`, `htf_trend`.
  - [x] Added `mtfa` field to `ContextPack` with `to_dict()` support.
  - [x] `ContextPackBuilder._compute_mtfa()` computes alignment score as fraction of timeframes agreeing with majority direction.
  - [x] Returns `MTFAContext()` with `alignment_score=None` when fewer than 2 timeframes have regime data.

- [x] **`RegimeFitEvaluator` (`src/evaluators/regime_fit.py`)**
  - [x] Registered with `@register_evaluator("regime_fit")`.
  - [x] REG001: Trade direction conflicts with regime label (skips for generic labels).
  - [x] REG002: High transition risk above threshold (default 0.3).
  - [x] REG003: High entropy above threshold (default 1.5) — INFO severity.
  - [x] REG004: OOD detected — market outside model training range.

- [x] **`MTFAEvaluator` (`src/evaluators/mtfa.py`)**
  - [x] Registered with `@register_evaluator("mtfa")`.
  - [x] MTFA001: Low alignment (< 0.6) — timeframe disagreement WARNING.
  - [x] MTFA002: High alignment (>= 0.8) — positive confirmation INFO.
  - [x] MTFA003: HTF (1Hour/1Day) regime has high transition risk.

- [x] **API Updates**
  - [x] `GET /api/trading-buddy/regime?symbol=&timeframe=` — returns current regime snapshot.
  - [x] `GET /api/trading-buddy/key-levels?symbol=&timeframe=` — returns current key levels with VWAP.
  - [x] `/evaluate` context_summary includes `regimes` dict and `mtfa` when `include_context=True`.

---

## Phase 3: Entry Quality + Missing Scanner

**Goal**: Refine entry tactics and ensure pre-flight checklist coverage.

- [ ] **Entry Quality Evaluator (`src/evaluators/entry_quality.py`)**
  - [ ] Register with `@register_evaluator("entry_quality")`.
  - [ ] Check entry location relative to Key Levels (support/resistance proximity).
  - [ ] Check extension from means (e.g., distance from 20 EMA, VWAP).
  - [ ] Check microstructure (volume profile, bid/ask imbalances if data available).
  - [ ] Use `context.key_levels.distance_to_nearest_level()` and feature data from `context.get_feature()`.

- [ ] **Missing Scanner Evaluator (`src/evaluators/missing_scanner.py`)**
  - [ ] Register with `@register_evaluator("missing_scanner")`.
  - [ ] "Did you check X?" logic — items the trader should have considered.
  - [ ] Check for upcoming high-impact economic events (Calendar integration — may need external data source).
  - [ ] Check liquidity conditions (e.g., volume vs average, spread proxies from features).
  - [ ] Check whether the trader reviewed key levels, regime, and MTFA context (based on `ContextPack` availability).

## Phase 4: Strategy Consistency + Playbooks (Personalization)

**Goal**: Learn user style and detect drift.

- [ ] **Database Expansion**
  - [ ] Add `strategy_profiles`, `playbooks`, `playbook_members` tables.
  - [ ] Update Alembic migrations.

- [ ] **Strategy Profiling Jobs (`src/profiling/`)**
  - [ ] Implement `StrategyProfileBuilder`:
    - [ ] Aggregate past trade stats (from `trade_fills` synced via SnapTrade or manual entries).
    - [ ] Compute win/loss behavior distributions.
  - [ ] Implement `PlaybookClusterer`:
    - [ ] Generate trade vectors (embeddings) from attributes.
    - [ ] Cluster using HDBSCAN or K-Means.
    - [ ] Save centroids as Playbooks.

- [ ] **Strategy Consistency Evaluator (`src/evaluators/strategy_consistency.py`)**
  - [ ] Register with `@register_evaluator("strategy_consistency")`.
  - [ ] Compare current `TradeIntent` to `Playbooks`.
  - [ ] Calculate "OOD" (Out of Distribution) score.
  - [ ] Generate "Resembles Playbook X" message.

## Phase 5: Correlation & Portfolio Exposure

**Goal**: Manage portfolio-level risk.

- [ ] **Database Expansion**
  - [ ] Add `positions` and `portfolio_exposure_snapshots` tables.

- [ ] **Portfolio Exposure Engine**
  - [ ] Implement `PortfolioExposureBuilder`:
    - [ ] Calculate gross/net exposure.
    - [ ] Compute beta to benchmark.
    - [ ] Compute correlations between open positions.
  - [ ] Can leverage positions data from SnapTrade broker integration (`BrokerConnection` accounts).

- [ ] **Correlation Evaluator (`src/evaluators/correlation.py`)**
  - [ ] Register with `@register_evaluator("correlation")`.
  - [ ] Check for "Stacking" (adding risk to correlated assets).
  - [ ] Check total exposure limits.

## Phase 6: Behavioral Nudges

**Goal**: Detect and mitigate psychological pitfalls.

- [ ] **Behavior Engine (`src/behavior/`)**
  - [ ] Implement detectors for:
    - [ ] Overtrading (high frequency).
    - [ ] Revenge Trading (trading immediately after loss).
    - [ ] FOMO (chasing parabolic moves).
  - [ ] Define `BehaviorEvent` model and logging.
  - [ ] Use `trade_fills` (from broker sync) and `trade_intents` for behavioral pattern detection.

- [ ] **Behavior Nudges Evaluator (`src/evaluators/behavior.py`)**
  - [ ] Register with `@register_evaluator("behavior")`.
  - [ ] Inject specific warning messages based on detected recent behavior.

## Phase 7: Post-Trade Review + Learning Loop

**Goal**: Automate reflection and improvement.

- [ ] **Review Generator (`src/review/`)**
  - [ ] Implement `PostTradeReviewGenerator`:
    - [ ] Calculate MAE/MFE (Maximum Adverse/Favorable Excursion).
    - [ ] Grade "Process" vs "Outcome".
    - [ ] Auto-generate "What went well" / "What to improve".
  - [ ] Link reviews to original `TradeEvaluation` (requires persistence from Phase 0 gap fix).

- [ ] **Database Expansion**
  - [ ] Add `post_trade_reviews` table.

## Phase 8: Conversational Brainstorm Mode

**Goal**: Full Agentic UX.

- [ ] **Assistant Infrastructure**
  - [ ] Add `assistant_sessions`, `assistant_messages` tables.
  - [ ] Implement `IntentRouter` (Brainstorm vs Evaluate vs Review).
  - [ ] Integrate LLM for "Slot Filling" (Turn chat into `TradeIntent`).

- [ ] **Interactive Session Handling**
  - [ ] Implement `POST /api/trading-buddy/assistant-session`.
