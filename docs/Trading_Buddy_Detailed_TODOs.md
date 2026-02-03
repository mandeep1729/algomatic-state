# Trading Buddy Platform - Detailed Implementation TODOs

Based on the [Master Roadmap](./Trading_Buddy_Master_Roadmap_and_DB_Schema.md) and current codebase analysis.

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
| **HMM Inference** | `src/hmm/inference.py::InferenceEngine` | State vectors, regime probabilities, OOD detection |
| **Multi-TF Inference** | `src/hmm/inference.py::MultiTimeframeInferenceEngine` | HTF state carry-forward with TTL |
| **Existing API** | `ui/backend/api.py` | Extend with new Trading Buddy endpoints |

### Key Integration Notes

1. **ContextPackBuilder** should use:
   - `OHLCVRepository.get_bars()` for latest OHLCV
   - `OHLCVRepository.get_features()` for TA indicators
   - `OHLCVRepository.get_states()` for HMM regime data
   - `InferenceEngine` or `MultiTimeframeInferenceEngine` for live regime inference

2. **Database additions** should be in a **new Alembic migration** (e.g., `005_trading_buddy_tables.py`) extending the existing schema, not replacing it.

3. **Key Levels** computation can leverage existing `FeaturePipeline` infrastructure.

4. **API endpoints** should be added to `ui/backend/api.py` using FastAPI patterns already established.

---

## Phase 0: Foundations (Core Platform)

**Goal**: Establish the core infrastructure, database schema, and evaluation orchestration engine.

- [ ] **Database Schema Expansion**
  - [ ] Create new Alembic migration script for Trading Buddy tables.
  - [ ] Implement SQLAlchemy models in `src/data/database/models.py` (or `src/data/database/trading_buddy_models.py` if preferred for separation):
    - [ ] `UserAccount` (`user_accounts`)
    - [ ] `UserRule` (`user_rules`)
    - [ ] `TradeIntent` (`trade_intents`)
    - [ ] `TradeEvaluation` (`trade_evaluations`)
    - [ ] `TradeEvaluationItem` (`trade_evaluation_items`)
  - [ ] Run migration to apply changes.

- [ ] **Core Domain Objects (`src/trade/`)**
  - [ ] Define `TradeIntent` Pydantic model in `src/trade/intent.py`.
  - [ ] Define `EvaluationResult` dataclass in `src/trade/evaluation.py`.
  - [ ] Define `Evidence` structure in `src/trade/evaluation.py`.

- [ ] **ContextPack Infrastructure (`src/evaluators/context.py`)**
  - [ ] Implement `ContextPack` class (data container).
  - [ ] Implement `ContextPackBuilder` class.
    - [ ] Use `OHLCVRepository.get_bars()` and `OHLCVRepository.get_features()` for OHLCV + TA data.
    - [ ] Use `OHLCVRepository.get_states()` or `InferenceEngine` for HMM regime context.
    - [ ] Implement Caching (in-memory or Redis) for ContextPack to avoid re-querying for same user/symbol/timeframe.

- [ ] **Evaluator Engine (`src/evaluators/`)**
  - [ ] Create `base.py` with `Evaluator` abstract base class.
    - [ ] `evaluate(intent: TradeIntent, context: ContextPack) -> EvaluationResult`
  - [ ] Create `registry.py` for registering and retrieving evaluator modules.
  - [ ] Create `evidence.py` for utility functions (z-score calculation, threshold checking).

- [ ] **Orchestrator (`src/orchestrator.py`)**
  - [ ] Implement `EvaluatorOrchestrator` class.
    - [ ] Load configured evaluators.
    - [ ] Run evaluations in parallel (optional) or sequence.
    - [ ] Aggregate results (deduplicate issues, compute overall score).
    - [ ] Generate summary.

- [ ] **API/UI Shell**
  - [ ] Create API endpoints (FastAPI router):
    - [ ] `POST /tradeIntents` (Draft/Submit)
    - [ ] `POST /evaluateTradeIntent`
  - [ ] Create basic "Evaluate" specific endpoint to return top 3 issues + score.

## Phase 1: Trust + Risk-First MVP

**Goal**: Implement the critical safety checks to deliver immediate value.

- [ ] **Risk & Reward Evaluator (`src/evaluators/risk_reward.py`)**
  - [ ] Implement `RiskRewardEvaluator`.
    - [ ] Check R:R ratio against minimums.
    - [ ] Check position size vs account risk limits (from `UserAccount` defaults).
    - [ ] Check stop loss distance vs ATR/volatility check.

- [ ] **Exit Plan Evaluator (`src/evaluators/exit_plan.py`)**
  - [ ] Implement `ExitPlanEvaluator`.
    - [ ] Verify existence of Stop Loss and Profit Target.
    - [ ] specific checks for coherence (Target > Entry for Long, etc.).

- [ ] **User Configuration**
  - [ ] Implement logic to load/apply `UserRules` and `UserAccount` risk defaults during evaluation.

- [ ] **Guardrails (`src/rules/guardrails.py`)**
  - [ ] Implement output sanitization (ensure no deterministic predictions).
  - [ ] Add warning templates for high-risk flags.

## Phase 2: MTFA + Regime + Key Levels

**Goal**: Integrate market context (Regime, MTFA, Levels) into the evaluation.

- [ ] **Key Levels Engine (`src/features/key_levels.py`)**
  - [ ] Implement computation logic for (can derive from existing `OHLCVRepository.get_bars()` data):
    - [ ] Prior Day High/Low/Close.
    - [ ] Pivot Points.
    - [ ] Rolling Range (e.g., 20-day high/low).
    - [ ] Anchored VWAP (uses existing `vwap_60` feature or extend).
  - [ ] Optionally add to `FeaturePipeline` as a new calculator, or compute on-the-fly in `ContextPackBuilder`.

- [ ] **Regime Integration** (leverages existing `src/hmm` module)
  - [ ] Use `InferenceEngine.process()` or `OHLCVRepository.get_states()` in `ContextPackBuilder`.
  - [ ] Transition Risk: derive from `hmm.hmm_model.GaussianHMMWrapper.transmat_` (off-diagonal probabilities).
  - [ ] Expose posterior entropy from `HMMOutput.state_probs` as uncertainty metric.

- [ ] **MTFA Integration** (uses existing `MultiTimeframeInferenceEngine`)
  - [ ] Use `MultiTimeframeInferenceEngine.get_all_states()` for cross-timeframe regime context.
  - [ ] Implement trend alignment: compare HTF `state_id` vs LTF `state_id` for trend/range classification.

- [ ] **Evaluator Implementation**
  - [ ] `RegimeFitEvaluator` (`src/evaluators/regime_fit.py`):
    - [ ] Warn if trading against strong regime (e.g., Long in Bear Trend).
    - [ ] Warn if "Transition Risk" is high.
  - [ ] `MTFAEvaluator` (`src/evaluators/mtfa.py`):
    - [ ] Score alignment between Setup Timeframe and HTF.

- [ ] **API Updates**
  - [ ] `GET /regimeSnapshot`
  - [ ] `GET /keyLevels`

## Phase 3: Entry Quality + Missing Scanner

**Goal**: Refine entry tactics and ensure pre-flight checklist coverage.

- [ ] **Entry Quality Evaluator (`src/evaluators/entry_quality.py`)**
  - [ ] Check entry location relative to Key Levels (support/resistance).
  - [ ] Check extension from means (e.g., MA distance).
  - [ ] Check microstructure (volume profile, bid/ask imbalances if data available).

- [ ] **Missing Scanner Evaluator (`src/evaluators/missing_scanner.py`)**
  - [ ] "Did you check X?" logic.
  - [ ] Check for upcoming high-impact economic events (Calendar integration).
  - [ ] Check liquidity conditions.

## Phase 4: Strategy Consistency + Playbooks (Personalization)

**Goal**: Learn user style and detect drift.

- [ ] **Database Expansion**
  - [ ] Add `strategy_profiles`, `playbooks`, `playbook_members` tables.
  - [ ] Update Alembic migrations.

- [ ] **Strategy Profiling Jobs (`src/profiling/`)**
  - [ ] Implement `StrategyProfileBuilder`:
    - [ ] Aggregate past trade stats.
    - [ ] Compute win/loss behavior distributions.
  - [ ] Implement `PlaybookClusterer`:
    - [ ] Generate trade vectors (embeddings) from attributes.
    - [ ] Cluster using HDBSCAN or K-Means.
    - [ ] Save centroids as Playbooks.

- [ ] **Strategy Consistency Evaluator (`src/evaluators/strategy_consistency.py`)**
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

- [ ] **Correlation Evaluator (`src/evaluators/correlation.py`)**
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

- [ ] **Behavior Nudges Evaluator (`src/evaluators/behavior.py`)**
  - [ ] Inject specific warning messages based on detected recent behavior.

## Phase 7: Post-Trade Review + Learning Loop

**Goal**: Automate reflection and improvement.

- [ ] **Review Generator (`src/review/`)**
  - [ ] Implement `PostTradeReviewGenerator`:
    - [ ] Calculate MAE/MFE (Maximum Adverse/Favorable Excursion).
    - [ ] Grade "Process" vs "Outcome".
    - [ ] Auto-generate "What went well" / "What to improve".

- [ ] **Database Expansion**
  - [ ] Add `post_trade_reviews` table.

## Phase 8: Conversational Brainstorm Mode

**Goal**: Full Agentic UX.

- [ ] **Assistant Infrastructure**
  - [ ] Add `assistant_sessions`, `assistant_messages` tables.
  - [ ] Implement `IntentRouter` (Brainstorm vs Evaluate vs Review).
  - [ ] Integrate LLM for "Slot Filling" (Turn chat into `TradeIntent`).

- [ ] **Interactive Session Handling**
  - [ ] Implement `POST /assistantSession`.
