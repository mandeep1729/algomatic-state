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
 */
const api = USE_MOCKS
  ? mockApi
  : {
      // Real backend endpoints
      evaluateTrade: realApi.evaluateTrade,
      fetchEvaluators: realApi.fetchEvaluators,
      fetchBrokerStatus: realApi.fetchBrokerStatus,

      // Mock fallbacks — no backend endpoints yet
      fetchCurrentUser: mockApi.fetchCurrentUser,
      fetchTradingProfile: mockApi.fetchTradingProfile,
      updateTradingProfile: mockApi.updateTradingProfile,
      fetchRiskPreferences: mockApi.fetchRiskPreferences,
      updateRiskPreferences: mockApi.updateRiskPreferences,
      fetchTrades: mockApi.fetchTrades,
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
    };

export default api;
