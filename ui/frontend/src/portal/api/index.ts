import { USE_MOCKS } from '../mocks/enable';
import * as mockApi from '../mocks/mockApi';
import * as realApi from './client';

/**
 * Hybrid API layer.
 *
 * When VITE_USE_MOCKS=true (default): all functions use mocks.
 * When VITE_USE_MOCKS=false: uses real backend for endpoints that exist,
 * falls back to mocks for everything else.
 *
 * Real backend endpoints available:
 *   - evaluateTrade      → POST /api/trading-buddy/evaluate
 *   - fetchEvaluators    → GET  /api/trading-buddy/evaluators
 *   - fetchBrokerStatus  → GET  /api/broker/status
 *   - fetchTrades        → GET  /api/broker/trades
 *   - fetchSyncStatus    → GET  /api/sync-status/{symbol}
 *   - triggerSync        → POST /api/sync/{symbol}
 *   - fetchOHLCVData     → GET  /api/ohlcv/{symbol}
 *   - fetchFeatures      → GET  /api/features/{symbol}
 */
const api = USE_MOCKS
  ? mockApi
  : {
      // Real backend endpoints
      evaluateTrade: realApi.evaluateTrade,
      fetchEvaluators: realApi.fetchEvaluators,
      fetchBrokerStatus: realApi.fetchBrokerStatus,
      fetchTrades: realApi.fetchTrades,

      // Mock fallbacks — no backend endpoints yet
      fetchCurrentUser: mockApi.fetchCurrentUser,
      fetchTradingProfile: mockApi.fetchTradingProfile,
      updateTradingProfile: mockApi.updateTradingProfile,
      fetchRiskPreferences: mockApi.fetchRiskPreferences,
      updateRiskPreferences: mockApi.updateRiskPreferences,
      fetchTradeDetail: mockApi.fetchTradeDetail,
      createManualTrade: mockApi.createManualTrade,
      fetchInsightsSummary: mockApi.fetchInsightsSummary,
      fetchRegimeInsights: mockApi.fetchRegimeInsights,
      fetchTimingInsights: mockApi.fetchTimingInsights,
      fetchBehavioralInsights: mockApi.fetchBehavioralInsights,
      fetchRiskInsights: mockApi.fetchRiskInsights,
      fetchStrategyDriftInsights: mockApi.fetchStrategyDriftInsights,
      fetchJournalEntries: mockApi.fetchJournalEntries,
      createJournalEntry: mockApi.createJournalEntry,
      updateJournalEntry: mockApi.updateJournalEntry,
      fetchBehavioralTags: mockApi.fetchBehavioralTags,
      fetchStrategies: mockApi.fetchStrategies,
      createStrategy: mockApi.createStrategy,
      updateStrategy: mockApi.updateStrategy,
      fetchEvaluationControls: mockApi.fetchEvaluationControls,
      updateEvaluationControls: mockApi.updateEvaluationControls,
      fetchOnboardingStatus: mockApi.fetchOnboardingStatus,
      fetchTickerPnl: mockApi.fetchTickerPnl,
      fetchTickerPnlTimeseries: mockApi.fetchTickerPnlTimeseries,
    };

export default api;

// Re-export real chart data functions from client
export { fetchSyncStatus, triggerSync, fetchOHLCVData, fetchFeatures } from './client';

// Re-export mock chart data helpers for fallback use
export { fetchMockOHLCVData, fetchMockFeatures } from '../mocks/mockApi';

// Re-export PnL timeseries for direct use
export { fetchTickerPnlTimeseries } from '../mocks/mockApi';
