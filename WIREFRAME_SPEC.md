# TradingBuddy Analytics Platform

## UI Wireframe Specification

Version: 1.0\
Purpose: Define structured layout, components, and interaction logic for
the TradingBuddy coaching analytics dashboard.

------------------------------------------------------------------------

# 1. Information Architecture

## Top Navigation

-   Dashboard
-   Trades
-   Strategies
-   Tickers
-   Intelligence
-   Coaching

## Global Controls (Persistent Header)

-   Account Selector
-   Date Range Selector
-   Ticker Filter
-   Strategy Filter
-   Regime Filter
-   Export Button

------------------------------------------------------------------------

# 2. Main Dashboard (Executive View)

## Layout Grid

Row 1: - Equity Curve (60% width) - Key Metrics Panel (40% width)

Row 2: - Drawdown Chart (50%) - Rolling Sharpe Ratio (50%)

Row 3: - Trade Return Distribution (50%) - Holding Period vs Return
Scatter (50%)

Row 4: - Time-of-Day PnL Heatmap (100%)

## Key Metrics Panel

-   Total Net PnL
-   Win Rate
-   Expectancy
-   Sharpe Ratio
-   Max Drawdown
-   Avg Hold Time
-   Avg R Multiple
-   Emotional Stability Score
-   Entry Quality Score

Color coding: - Green: Strong Edge - Yellow: Unstable - Red: Broken
Component

------------------------------------------------------------------------

# 3. Strategy Page

## Purpose

Evaluate which strategies have real edge.

## Layout

Row 1: - Strategy Risk vs Return Bubble Chart (60%) - Strategy Summary
Table (40%)

Row 2: - Strategy Equity Curve (100%)

Row 3: - Strategy by Regime Breakdown (50%) - Strategy Return
Distribution (50%)

## Strategy Table Columns

-   Strategy Name
-   Trades
-   Win Rate
-   Avg Return
-   Sharpe Ratio
-   Max Drawdown
-   Avg Hold Time
-   Regime Sensitivity Score

------------------------------------------------------------------------

# 4. Ticker Intelligence Page

## Purpose

Identify personal edge by ticker.

## Layout

Row 1: - Ticker Risk vs Return Scatter (60%) - Cluster Mode Toggle (40%)

Row 2: - Ticker Performance Heatmap (100%)

Row 3: - Correlation Matrix (50%) - Holding Period vs Return (50%)

## Cluster Modes

-   Return + Volatility
-   Holding Period + Return
-   Regime Sensitivity

------------------------------------------------------------------------

# 5. Trade Intelligence Page

## Purpose

Diagnose execution quality and mistakes.

## Layout

Row 1: - MAE vs MFE Scatter (50%) - Entry Quality Distribution (50%)

Row 2: - Breakout Distance vs Return (50%) - Stop Size vs R Multiple
(50%)

Row 3: - Late Entry Detection Table (100%)

## Late Entry Table Columns

-   Ticker
-   Distance from VWAP
-   Distance from Breakout Level
-   Momentum Exhaustion Flag
-   Trade Outcome
-   Late Entry Score

------------------------------------------------------------------------

# 6. Emotional & Behavioral Page

## Purpose

Measure psychological impact on performance.

## Layout

Row 1: - Boredom Index vs Return (50%) - Time Since Last Trade vs
Outcome (50%)

Row 2: - Performance After Loss (50%) - Revenge Trade Indicator (50%)

Row 3: - Emotional State vs Performance Table (100%)

------------------------------------------------------------------------

# 7. Clustering & State Intelligence Page

## Purpose

Visualize trade clusters and regime-driven behavior.

## Layout

Left Sidebar: - Feature Selection Panel - Clustering Algorithm Selector
(KMeans / HDBSCAN) - Regime Filter

Main View: - UMAP or t-SNE Projection (80%) - Cluster Summary Panel
(20%)

Bottom Section: - Cluster Performance Summary Table (100%)

## Cluster Summary Fields

-   Cluster ID
-   Trade Count
-   Avg Return
-   Avg Holding Period
-   Regime Distribution
-   Entry Quality Mean

------------------------------------------------------------------------

# 8. UX Principles

-   Visual-first analytics
-   Minimal clutter
-   Clear color-coded coaching signals
-   Tooltips explaining metric relevance
-   Regime toggle available on all charts
-   Click-through drill-down everywhere

------------------------------------------------------------------------

# 9. Responsive Design Behavior

Desktop: - Multi-column grid layout

Tablet: - Stacked charts - Collapsible filters

Mobile: - Summary metrics first - Single-chart view with swipe
navigation

------------------------------------------------------------------------

# 10. AI Coaching Panel (Optional Enhancement)

Each page includes a contextual AI Insight Box:

Examples: - "Your breakout strategy performs 2.4x better in high
volatility regimes." - "You lose 63% of trades entered more than 1.2%
above VWAP." - "Holding trades beyond 3 days reduces expectancy by 38%."

This transforms analytics into actionable coaching.

------------------------------------------------------------------------

End of WIREFRAME_SPEC.md
