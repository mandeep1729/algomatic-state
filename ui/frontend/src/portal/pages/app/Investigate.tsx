/**
 * Investigate page — drill-down analytics with filter→recompute paradigm.
 *
 * Single route /app/investigate with 4 tabs:
 *   Overview | Trade Explorer | Strategy Lab | Behavior Lab
 *
 * Wrapped in InvestigateProvider for shared state.
 */

import { useSearchParams } from 'react-router-dom';
import { InvestigateProvider, useInvestigate } from '../../context/InvestigateContext';
import { FilterBar } from '../../components/investigate/FilterBar';
import { SubsetMetrics } from '../../components/investigate/SubsetMetrics';
import { WhyPanel } from '../../components/investigate/WhyPanel';
import { OverviewTab } from '../../components/investigate/OverviewTab';
import { TradeExplorerTab } from '../../components/investigate/TradeExplorerTab';
import { StrategyLabTab } from '../../components/investigate/StrategyLabTab';
import { BehaviorLabTab } from '../../components/investigate/BehaviorLabTab';

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'explorer', label: 'Trade Explorer' },
  { key: 'strategy', label: 'Strategy Lab' },
  { key: 'behavior', label: 'Behavior Lab' },
] as const;

type TabKey = (typeof TABS)[number]['key'];

function InvestigateContent() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = (searchParams.get('tab') ?? 'overview') as TabKey;
  const { loading, error } = useInvestigate();

  function setTab(tab: TabKey) {
    setSearchParams({ tab }, { replace: true });
  }

  if (loading) {
    return (
      <div className="flex h-[400px] items-center justify-center text-sm text-[var(--text-secondary)]">
        Loading investigation data...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-[var(--accent-red)]/30 bg-[var(--accent-red)]/5 p-4 text-sm text-[var(--accent-red)]">
          Error loading data: {error}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Title + Tabs */}
        <div className="px-6 pt-6 pb-0">
          <h1 className="mb-4 text-2xl font-semibold">Investigate</h1>

          {/* Tab bar */}
          <div className="flex gap-1 border-b border-[var(--border-color)]">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setTab(tab.key)}
                className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
                  activeTab === tab.key
                    ? 'border-[var(--accent-blue)] text-[var(--accent-blue)]'
                    : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Filter bar */}
        <FilterBar />

        {/* Subset metrics strip */}
        <div className="py-3">
          <SubsetMetrics />
        </div>

        {/* Tab content (scrollable) */}
        <div className="flex-1 overflow-y-auto px-6 pb-6">
          {activeTab === 'overview' && <OverviewTab />}
          {activeTab === 'explorer' && <TradeExplorerTab />}
          {activeTab === 'strategy' && <StrategyLabTab />}
          {activeTab === 'behavior' && <BehaviorLabTab />}
        </div>
      </div>

      {/* WHY Panel (right sidebar) */}
      <WhyPanel />
    </div>
  );
}

export default function Investigate() {
  return (
    <InvestigateProvider>
      <InvestigateContent />
    </InvestigateProvider>
  );
}
