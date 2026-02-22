# CLAUDE.md

## vibeflow Agent Session Rules

**CRITICAL — When a vibeflow session_init prompt is active (autonomous agent mode), these rules apply to ALL work, including ad-hoc user requests:**

1. **NEVER write code, enter plan mode, or use EnterPlanMode before creating a tracked work item in vibeflow.** If the user asks you to build, fix, add, or modify anything, your FIRST action must be to classify it (feature todo or issue) and create it in vibeflow via the MCP tools. No exceptions.

2. **The ad-hoc request workflow in the agent prompt takes ABSOLUTE PRIORITY over Claude Code's built-in planning tools.** Do not use EnterPlanMode until after the vibeflow work item exists and has been transitioned to `implementing` status.

3. **Every piece of work must flow through vibeflow status transitions** (planning → implementing → done), with execution logs published, git commits tracked, and line counts passed — even for "small" or "quick" changes.

4. **When polling for work, always drill into features to check todos.** `list_features` returns containers, not work items. For each feature returned with `ready_to_implement` or `implementing` status, call `list_todos(feature_id, status: "ready_to_implement,implementing")` to find actual work items. Never treat an empty `list_issues` result as "no work" without also checking todos inside returned features.

5. **YOU MUST use filters for tool calls to optimize data fetch.** Example: when listing_features to find items ready for work, filter by status so you only get features that are ready.

6. **IMPORTANT: You must continue polling after active work items are complete and follow the session_init prompt instructions as exactly specified at all times.**

7. **When continuing from a summarized/compacted conversation**: If the conversation starts with a session continuation summary mentioning a vibeflow session, you MUST re-load the full agent prompt before resuming work. Do this by:
   a. Read `.vibeflow-session` from the working directory to get the existing session_id
   b. Call `session_init(project_name, session_id)` to get the full agent prompt
   c. Re-read the returned `prompt` field to reload Phase 1-4 instructions
   d. Skip Phase 1 steps already done (project lookup, etc.) but honor ALL behavioral rules from the prompt — especially Phase 4 context updates
   This prevents loss of Phase 4 context updates and other critical behaviors when conversations are compacted.


## Skills

See @.claude/skills/coding-best-practices/SKILLS.md for coding best practices and design patterns.

## Role

See @.claude/SOFTWARE-ROLE.md for your role


## Project Overview

This project builds a trading copilot / assistant whose primary role is to improve trading decisions by surfacing risk, context, and inconsistencies, not by predicting prices or generating trading signals.

Retail short‑term traders (e.g., app‑based traders with minimal structure) consistently lose money not because of a lack of indicators, but due to **behavioral mistakes, poor risk discipline, and lack of contextual awareness**.

**Goal:** Build a trading mentor platform that prevents *no‑brainer bad trades*, reinforces discipline, and teaches users *when not to trade* — without becoming a signal‑selling platform.

The system acts as a **mentor + risk guardian + behavioral coach**, not a predictor.

The system acts as a second set of eyes — quietly reviewing a proposed trade and highlighting what the trader may have overlooked.

### The assistant is:

- Risk-first
- Process-oriented
- Non-predictive
- Trader-specific over time
- Prevent obvious mistakes before execution
- Explain *why* a trade is bad in plain language
- Focus on habits and discipline, not trade ideas
- Be broker‑agnostic and strategy‑agnostic
- Simple, explainable rules before advanced AI

### What This Project Is NOT
- The assistant must never:
- Predict price direction
- Claim high-probability outcomes
- Generate buy/sell signals
- Replace trader judgment
- Optimize for win rate alone
- This is not a signal service, alpha engine, or automated trading system.

### Core Product Philosophy

“Slow the trader down, not tell them what to do.”

### The assistant exists to:

- Improve decision quality
- Reduce preventable mistakes
- Encourage discipline and consistency
- Surface contextual risk
- Build long-term trader trust

## Codebase Structure

The project has the following major subsystems:

1. **Regime Tracking Engine** (`src/features/state/hmm/`, `src/features/state/pca/`) -- HMM and PCA-based market state inference from engineered features. The feature pipeline is in `src/features/`.

2. **Trading Buddy** (`src/evaluators/`, `src/orchestrator.py`, `src/trade/`, `src/rules/`, `src/api/trading_buddy.py`) -- Modular trade evaluation system. Pluggable evaluators check risk/reward, exit plans, regime fit, and multi-timeframe alignment. Guardrails enforce the no-prediction policy.

3. **Messaging & Market Data Service** (`src/messaging/`, `src/marketdata/`) -- In-memory pub/sub message bus decoupling market data fetching from consumers. `MarketDataOrchestrator` coordinates between the bus and `MarketDataService`.

4. **Trade Lifecycle & Campaigns** (`src/api/campaigns.py`, `src/data/database/trade_lifecycle_models.py`) -- Tracks trade journeys from flat-to-flat using fills as the atomic unit. Decision contexts capture trader reasoning per fill, campaign_fills provides derived FIFO zero-crossing groupings. Behavioral checks (`src/checks/`, `src/reviewer/`) run against decision contexts.

5. **Reviewer Service** (`src/reviewer/`) -- Event-driven service that subscribes to review events on the Redis message bus and runs behavioral checks against trade fills and decision contexts.

6. **Go Data Service** (`data-service/`, `proto/`) -- gRPC service (Go) that owns all market data tables (`tickers`, `ohlcv_bars`, `computed_features`, `data_sync_log`, probe tables). All Python market data access flows through `MarketDataGrpcClient` (`src/data/grpc_client.py`) via gRPC. Trading tables remain in Python via SQLAlchemy repositories.

7. **Go Market Data Service** (`marketdata-service/`) -- Go service that fetches market data from Alpaca, aggregates timeframes, and writes to the data-service via gRPC.

8. **Go Agent Service** (`agent-service/`) -- Go service that manages trading agent lifecycle. Polls for active agents, resolves their strategy definitions, runs agent loops (fetch data, compute signals, submit orders via Alpaca), and tracks orders and activity. Repositories: `agent_repo`, `order_repo`, `activity_repo`, `strategy_repo`.

9. **Trading Agents Management** (`src/trading_agents/`, `src/api/trading_agents.py`) -- Python models, repository, and API for managing trading agent configurations. Predefined strategy catalog (`predefined.py`), agent CRUD, lifecycle control (start/pause/stop), and order/activity endpoints.

10. **Portal UI** (`ui/frontend/src/portal/`) -- Full SPA built with React + TypeScript. Public pages (landing, FAQ, how-it-works), Google OAuth login, app pages (dashboard, campaigns, investigate/insights, journal, agents, strategy probe, evaluate), settings (profile, risk, strategies, brokers), and help section.

Supporting infrastructure: data loaders (`src/data/`), database models and repositories (`src/data/database/`), repository layer (`BrokerRepository`, `JournalRepository`, `ProbeRepository`, `TradingBuddyRepository`), unified dependency injection (`src/data/database/dependencies.py`), broker integration (`src/api/broker.py`, `src/api/alpaca.py`, `src/execution/snaptrade_client.py`), backtesting (`src/backtest/`), configuration (`config/settings.py`), authentication (`src/api/auth.py`, `src/api/auth_middleware.py`).

Additional components:
- `go-strats/` -- Go strategy backtesting framework (uses gRPC for persistence)
- `indicator-engine/` -- C++ high-performance indicator computation (gRPC client to data-service)

See `docs/ARCHITECTURE.md` for detailed architecture, and `docs/DATABASE.md` for detailed database schema and design details.
