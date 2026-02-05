# UI Requirements

Established UI behaviors and constraints for the frontend portal. These must be preserved during future changes.

## Chart (OHLCVChart)

### Timestamps & Timezone
- All timestamps from the backend must include the `Z` suffix (ISO 8601 UTC): `"%Y-%m-%dT%H:%M:%SZ"`
- All displayed times (x-axis labels, crosshair tooltip, slider labels) must be in **EST/EDT** (`America/New_York`), not UTC.
- Chart internally pre-shifts timestamps to EST-as-UTC so that lightweight-charts day boundaries align with EST days — date labels (e.g., "Feb 4") must appear at the start of that day's EST data, not at UTC midnight.

### Slider (range selector)
- The slider must remember its start and end positions across re-renders. It only resets when the underlying data actually changes (different ticker or timeframe), not on every React render cycle.
- There is no minimum number of visible chart points — the user can bring the slider handles as close together as they want (`MIN_CHART_POINTS = 1`).

## Trades Table

### Ticker-based filtering
- **When a ticker is selected and its chart is rendered, the trades table below must filter to show only trades for that ticker.** This applies to:
  - **Overview page** (`Overview.tsx`): The "Recent Trades" section re-fetches with the selected symbol filter. The section title updates to "Recent Trades — {TICKER}".
  - **Trades page** (`Trades.tsx`): The `effectiveSymbolFilter` combines `selectedTicker` with the manual symbol search filter.
- When the chart is closed (ticker deselected), the trades table reverts to showing all trades (unfiltered).
- Empty state messages must be contextual: "No trades found for {TICKER}" when filtered vs. generic message when unfiltered.
