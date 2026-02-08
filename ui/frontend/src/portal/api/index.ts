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
 *   - evaluateTrade            -> POST /api/trading-buddy/evaluate
 *   - fetchEvaluators          -> GET  /api/trading-buddy/evaluators
 *   - fetchBrokerStatus        -> GET  /api/broker/status
 *   - fetchTrades              -> GET  /api/broker/trades
 *   - fetchCampaigns           -> GET  /api/campaigns
 *   - fetchCampaignDetail      -> GET  /api/campaigns/{id}
 *   - saveDecisionContext      -> PUT  /api/campaigns/{id}/context
 *   - fetchUncategorizedCount  -> GET  /api/campaigns/uncategorized-count
 *   - fetchTickerPnl           -> GET  /api/campaigns/pnl/{symbol}
 *   - fetchTickerPnlTimeseries -> GET  /api/campaigns/pnl/timeseries
 *   - fetchSyncStatus          -> GET  /api/sync-status/{symbol}
 *   - triggerSync              -> POST /api/sync/{symbol}
 *   - fetchOHLCVData           -> GET  /api/ohlcv/{symbol}
 *   - fetchFeatures            -> GET  /api/features/{symbol}
 *   - fetchTradingProfile      -> GET  /api/user/profile
 *   - updateTradingProfile     -> PUT  /api/user/profile
 *   - fetchRiskPreferences     -> GET  /api/user/risk-preferences
 *   - updateRiskPreferences    -> PUT  /api/user/risk-preferences
 *   - fetchStrategies          -> GET  /api/user/strategies
 *   - createStrategy           -> POST /api/user/strategies
 *   - updateStrategy           -> PUT  /api/user/strategies/{id}
 *   - fetchEvaluationControls  -> GET  /api/user/evaluation-controls
 *   - updateEvaluationControls -> PUT  /api/user/evaluation-controls
 *   - fetchJournalEntries      -> GET  /api/journal/entries
 *   - createJournalEntry       -> POST /api/journal/entries
 *   - updateJournalEntry       -> PUT  /api/journal/entries/{id}
 *   - fetchBehavioralTags      -> GET  /api/journal/tags
 *   - fetchSitePrefs           -> GET  /api/user/site-prefs
 *   - updateSitePrefs          -> PUT  /api/user/site-prefs
 */
const api = USE_MOCKS
  ? mockApi
  : {
      // Real backend endpoints
      evaluateTrade: realApi.evaluateTrade,
      fetchEvaluators: realApi.fetchEvaluators,
      fetchBrokerStatus: realApi.fetchBrokerStatus,
      fetchTrades: realApi.fetchTrades,
      fetchTickerPnl: realApi.fetchTickerPnl,
      fetchTickerPnlTimeseries: realApi.fetchTickerPnlTimeseries,

      // Campaign endpoints -- real backend
      fetchCampaigns: realApi.fetchCampaigns,
      fetchCampaignDetail: realApi.fetchCampaignDetail,
      saveDecisionContext: realApi.saveDecisionContext,
      fetchUncategorizedCount: realApi.fetchUncategorizedCount,

      // User profile & settings -- real backend
      fetchTradingProfile: realApi.fetchTradingProfile,
      updateTradingProfile: realApi.updateTradingProfile,
      fetchRiskPreferences: realApi.fetchRiskPreferences,
      updateRiskPreferences: realApi.updateRiskPreferences,
      fetchStrategies: realApi.fetchStrategies,
      createStrategy: realApi.createStrategy,
      updateStrategy: realApi.updateStrategy,
      fetchEvaluationControls: realApi.fetchEvaluationControls,
      updateEvaluationControls: realApi.updateEvaluationControls,

      // Journal -- real backend
      fetchJournalEntries: realApi.fetchJournalEntries,
      createJournalEntry: realApi.createJournalEntry,
      updateJournalEntry: realApi.updateJournalEntry,
      fetchBehavioralTags: realApi.fetchBehavioralTags,

      // Site preferences -- real backend
      fetchSitePrefs: realApi.fetchSitePrefs,
      updateSitePrefs: realApi.updateSitePrefs,

      // Mock fallbacks -- no backend endpoints yet
      fetchCurrentUser: mockApi.fetchCurrentUser,
      fetchTradeDetail: mockApi.fetchTradeDetail,
      createManualTrade: mockApi.createManualTrade,
      fetchInsightsSummary: mockApi.fetchInsightsSummary,
      fetchRegimeInsights: mockApi.fetchRegimeInsights,
      fetchTimingInsights: mockApi.fetchTimingInsights,
      fetchBehavioralInsights: mockApi.fetchBehavioralInsights,
      fetchRiskInsights: mockApi.fetchRiskInsights,
      fetchStrategyDriftInsights: mockApi.fetchStrategyDriftInsights,
      fetchOnboardingStatus: mockApi.fetchOnboardingStatus,
    };

export default api;

// Re-export real chart data functions from client
export {
  fetchSyncStatus,
  triggerSync,
  fetchOHLCVData,
  fetchFeatures,
  fetchTickerPnlTimeseries,
} from './client';

// Re-export campaign OHLCV helper from client (uses real /api/ohlcv with date range)
export { fetchCampaignOHLCVData } from './client';

// Re-export mock chart data helpers for fallback use
export { fetchMockOHLCVData, fetchMockFeatures, fetchMockCampaignOHLCVData } from '../mocks/mockApi';

// Re-export mock PnL timeseries for fallback use
export { fetchTickerPnlTimeseries as fetchMockTickerPnlTimeseries } from '../mocks/mockApi';
