/**
 * InvestigateContext — single React context for the Investigate page.
 *
 * Manages:
 *  - Campaign + PnL data fetching
 *  - Filter chips (add / remove / clear)
 *  - Selection state (temporary chart highlight)
 *  - Compare mode toggle
 *  - Derived: subset, drivers, subsetMetrics (all via useMemo)
 */

import {
  createContext,
  useContext,
  useReducer,
  useEffect,
  useMemo,
  type ReactNode,
} from 'react';
import api, { fetchAggregatePnlTimeseries } from '../api';
import type { DailyPnlPoint } from '../api';
import type {
  CampaignSummary,
  InsightsSummary,
  TimingInsight,
  BehavioralInsight,
} from '../types';
import { applyFilters, createChip, type FilterChip, type FilterField, type FilterOp } from '../utils/investigateFilters';
import { computeSubsetMetrics, type SubsetMetrics } from '../utils/investigateMetrics';
import { computeDrivers, type Drivers } from '../utils/investigateDrivers';

// ---------------------------------------------------------------------------
// State & Actions
// ---------------------------------------------------------------------------

interface Selection {
  dimension: string;
  value: string;
}

interface InvestigateState {
  // Data
  allCampaigns: CampaignSummary[];
  pnlTimeseries: DailyPnlPoint[];
  insightsSummary: InsightsSummary | null;
  timingData: TimingInsight[];
  behavioralData: BehavioralInsight[];
  loading: boolean;
  error: string | null;

  // User state
  filters: FilterChip[];
  selection: Selection | null;
  compareEnabled: boolean;
}

type Action =
  | { type: 'SET_DATA'; campaigns: CampaignSummary[]; pnl: DailyPnlPoint[]; insights: InsightsSummary | null; timing: TimingInsight[]; behavioral: BehavioralInsight[] }
  | { type: 'SET_ERROR'; error: string }
  | { type: 'ADD_FILTER'; chip: FilterChip }
  | { type: 'REMOVE_FILTER'; chipId: string }
  | { type: 'CLEAR_FILTERS' }
  | { type: 'SET_SELECTION'; selection: Selection | null }
  | { type: 'TOGGLE_COMPARE' };

const initialState: InvestigateState = {
  allCampaigns: [],
  pnlTimeseries: [],
  insightsSummary: null,
  timingData: [],
  behavioralData: [],
  loading: true,
  error: null,
  filters: [],
  selection: null,
  compareEnabled: false,
};

function reducer(state: InvestigateState, action: Action): InvestigateState {
  switch (action.type) {
    case 'SET_DATA':
      return {
        ...state,
        allCampaigns: action.campaigns,
        pnlTimeseries: action.pnl,
        insightsSummary: action.insights,
        timingData: action.timing,
        behavioralData: action.behavioral,
        loading: false,
        error: null,
      };
    case 'SET_ERROR':
      return { ...state, loading: false, error: action.error };
    case 'ADD_FILTER':
      // Prevent duplicate chips with same field + value
      if (state.filters.some((f) => f.field === action.chip.field && JSON.stringify(f.value) === JSON.stringify(action.chip.value))) {
        return state;
      }
      return { ...state, filters: [...state.filters, action.chip] };
    case 'REMOVE_FILTER':
      return { ...state, filters: state.filters.filter((f) => f.id !== action.chipId) };
    case 'CLEAR_FILTERS':
      return { ...state, filters: [], selection: null };
    case 'SET_SELECTION':
      return { ...state, selection: action.selection };
    case 'TOGGLE_COMPARE':
      return { ...state, compareEnabled: !state.compareEnabled };
    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Context value shape
// ---------------------------------------------------------------------------

interface InvestigateContextValue {
  // Raw state
  allCampaigns: CampaignSummary[];
  pnlTimeseries: DailyPnlPoint[];
  insightsSummary: InsightsSummary | null;
  timingData: TimingInsight[];
  behavioralData: BehavioralInsight[];
  loading: boolean;
  error: string | null;
  filters: FilterChip[];
  selection: Selection | null;
  compareEnabled: boolean;

  // Derived
  subset: CampaignSummary[];
  drivers: Drivers;
  subsetMetrics: SubsetMetrics;
  allMetrics: SubsetMetrics;

  // Actions
  addFilter: (field: FilterField, op: FilterOp, value: FilterChip['value'], label: string, source?: FilterChip['source']) => void;
  removeFilter: (chipId: string) => void;
  clearFilters: () => void;
  setSelection: (sel: Selection | null) => void;
  toggleCompare: () => void;
}

const InvestigateCtx = createContext<InvestigateContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function InvestigateProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  // Fetch all data on mount
  useEffect(() => {
    async function load() {
      try {
        const [campaigns, pnl, insights, timing, behavioral] = await Promise.all([
          api.fetchCampaigns().catch(() => [] as CampaignSummary[]),
          fetchAggregatePnlTimeseries().catch(() => [] as DailyPnlPoint[]),
          api.fetchInsightsSummary().catch(() => null),
          api.fetchTimingInsights().catch(() => [] as TimingInsight[]),
          api.fetchBehavioralInsights().catch(() => [] as BehavioralInsight[]),
        ]);
        dispatch({ type: 'SET_DATA', campaigns, pnl, insights, timing, behavioral });
      } catch (err) {
        dispatch({ type: 'SET_ERROR', error: err instanceof Error ? err.message : 'Failed to load data' });
      }
    }
    load();
  }, []);

  // Derived state
  const subset = useMemo(
    () => applyFilters(state.allCampaigns, state.filters),
    [state.allCampaigns, state.filters],
  );

  const drivers = useMemo(() => computeDrivers(subset), [subset]);
  const subsetMetrics = useMemo(() => computeSubsetMetrics(subset), [subset]);
  const allMetrics = useMemo(() => computeSubsetMetrics(state.allCampaigns), [state.allCampaigns]);

  // Action helpers
  const addFilter = (field: FilterField, op: FilterOp, value: FilterChip['value'], label: string, source: FilterChip['source'] = 'manual') => {
    dispatch({ type: 'ADD_FILTER', chip: createChip(field, op, value, label, source) });
  };
  const removeFilter = (chipId: string) => dispatch({ type: 'REMOVE_FILTER', chipId });
  const clearFilters = () => dispatch({ type: 'CLEAR_FILTERS' });
  const setSelection = (sel: Selection | null) => dispatch({ type: 'SET_SELECTION', selection: sel });
  const toggleCompare = () => dispatch({ type: 'TOGGLE_COMPARE' });

  const value: InvestigateContextValue = {
    allCampaigns: state.allCampaigns,
    pnlTimeseries: state.pnlTimeseries,
    insightsSummary: state.insightsSummary,
    timingData: state.timingData,
    behavioralData: state.behavioralData,
    loading: state.loading,
    error: state.error,
    filters: state.filters,
    selection: state.selection,
    compareEnabled: state.compareEnabled,
    subset,
    drivers,
    subsetMetrics,
    allMetrics,
    addFilter,
    removeFilter,
    clearFilters,
    setSelection,
    toggleCompare,
  };

  return <InvestigateCtx.Provider value={value}>{children}</InvestigateCtx.Provider>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useInvestigate(): InvestigateContextValue {
  const ctx = useContext(InvestigateCtx);
  if (!ctx) throw new Error('useInvestigate must be used within InvestigateProvider');
  return ctx;
}
