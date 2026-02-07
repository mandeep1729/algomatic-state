# CLAUDE.md

See @.claude/skills/coding-best-practices/SKILLS.md for coding best practices and design patterns.
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

The project has three major subsystems:

1. **Regime Tracking Engine** (`src/features/state/hmm/`, `src/features/state/pca/`) -- HMM and PCA-based market state inference from engineered features. The feature pipeline is in `src/features/`.

2. **Trading Buddy** (`src/evaluators/`, `src/orchestrator.py`, `src/trade/`, `src/rules/`, `src/api/trading_buddy.py`) -- Modular trade evaluation system. Pluggable evaluators check risk/reward, exit plans, regime fit, and multi-timeframe alignment. Guardrails enforce the no-prediction policy.

3. **Standalone Momentum Agent** (`src/agent/`) -- Dockerised agent with a scheduler loop that fetches data (Alpaca or Finnhub via `src/marketdata/`), computes features, generates signals, and submits orders through the execution layer (`src/execution/`).

4. **Messaging & Market Data Service** (`src/messaging/`, `src/marketdata/`) -- In-memory pub/sub message bus decoupling market data fetching from consumers. `MarketDataOrchestrator` coordinates between the bus and `MarketDataService`.

5. **Position Campaigns & Trade Lifecycle** (`src/api/campaigns.py`, `src/data/database/trade_lifecycle_models.py`) -- Tracks trade journeys from flat-to-flat, with position lots, campaign legs, and decision contexts for post-trade analysis.

Supporting infrastructure: data loaders (`src/data/`), database models and repositories (`src/data/database/`), broker integration (`src/api/broker.py`, `src/api/alpaca.py`, `src/execution/snaptrade_client.py`), backtesting (`src/backtest/`), configuration (`config/settings.py`), authentication (`src/api/auth.py`, `src/api/auth_middleware.py`).

See `docs/ARCHITECTURE.md` for detailed architecture, and `docs/Trading_Buddy_Detailed_TODOs.md` for the Trading Buddy implementation roadmap.
