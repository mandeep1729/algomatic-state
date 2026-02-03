import { useState } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  ArrowRightLeft,
  ClipboardCheck,
  TrendingUp,
  BookOpen,
  Settings,
  User,
  Shield,
  Target,
  Link as LinkIcon,
  SlidersHorizontal,
  Lock,
  Search,
  Bell,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { appNavSections } from '../lib/nav';
import { MOCK_USER } from '../mocks/mockUser';
import { useChartContext } from '../context/ChartContext';
import { FeatureFilter } from '../../components/FeatureFilter';

// Map route paths to breadcrumb labels
const BREADCRUMB_LABELS: Record<string, string> = {
  '/app': 'Overview',
  '/app/trades': 'Trades',
  '/app/evaluate': 'Evaluate',
  '/app/insights': 'Insights',
  '/app/journal': 'Journal',
  '/app/settings/profile': 'Profile',
  '/app/settings/risk': 'Risk',
  '/app/settings/strategies': 'Strategies',
  '/app/settings/brokers': 'Brokers',
  '/app/settings/evaluation-controls': 'Evaluation Controls',
  '/app/settings/data-privacy': 'Data & Privacy',
};

function Breadcrumbs() {
  const location = useLocation();
  const path = location.pathname;

  const segments: { label: string; path: string }[] = [];

  if (path.startsWith('/app/settings')) {
    segments.push({ label: 'Settings', path: '/app/settings/profile' });
    const label = BREADCRUMB_LABELS[path];
    if (label && label !== 'Settings') {
      segments.push({ label, path });
    }
  } else if (path.startsWith('/app/trades/')) {
    segments.push({ label: 'Trades', path: '/app/trades' });
    segments.push({ label: 'Trade Detail', path });
  } else {
    const label = BREADCRUMB_LABELS[path];
    if (label) {
      segments.push({ label, path });
    }
  }

  if (segments.length === 0) return null;

  return (
    <div className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
      {segments.map((seg, i) => (
        <span key={seg.path} className="flex items-center gap-1.5">
          {i > 0 && <span>/</span>}
          {i === segments.length - 1 ? (
            <span className="text-[var(--text-primary)]">{seg.label}</span>
          ) : (
            <NavLink to={seg.path} className="hover:text-[var(--text-primary)]">
              {seg.label}
            </NavLink>
          )}
        </span>
      ))}
    </div>
  );
}

// Map nav icon name strings to Lucide components
const ICON_MAP: Record<string, LucideIcon> = {
  LayoutDashboard,
  ArrowRightLeft,
  ClipboardCheck,
  TrendingUp,
  BookOpen,
  Settings,
  User,
  Shield,
  Target,
  Link: LinkIcon,
  Sliders: SlidersHorizontal,
  Lock,
};

export default function AppLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const location = useLocation();
  const { chartActive, featureNames, selectedFeatures, onFeatureToggle } = useChartContext();

  const isSettingsActive = location.pathname.startsWith('/app/settings');

  return (
    <div className="flex h-screen bg-[var(--bg-primary)] text-[var(--text-primary)]">
      {/* Sidebar */}
      <aside
        className={`flex flex-shrink-0 flex-col border-r border-[var(--border-color)] bg-[var(--bg-secondary)] transition-all duration-200 ${
          sidebarCollapsed ? 'w-16' : 'w-60'
        }`}
      >
        {/* Logo / brand */}
        <div className="flex h-14 items-center justify-between border-b border-[var(--border-color)] px-4">
          {!sidebarCollapsed && (
            <span className="text-sm font-semibold tracking-wide">Trading Buddy</span>
          )}
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="flex h-7 w-7 items-center justify-center rounded text-[var(--text-secondary)] transition-colors duration-150 hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>

        {/* Nav + Feature Filter (shared scrollable area) */}
        <div className="flex-1 overflow-y-auto">
          <nav className="space-y-0.5 px-2 py-3">
            {appNavSections.map((item) => {
              const Icon = ICON_MAP[item.icon] ?? LayoutDashboard;

              // Settings with sub-nav
              if (item.children) {
                return (
                  <div key={item.path} className="mt-2">
                    <button
                      onClick={() => setSettingsOpen(!settingsOpen)}
                      className={`flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors duration-150 ${
                        isSettingsActive
                          ? 'bg-[var(--bg-tertiary)] text-[var(--text-primary)]'
                          : 'text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]'
                      }`}
                    >
                      <span className="flex w-5 justify-center">
                        <Icon size={18} />
                      </span>
                      {!sidebarCollapsed && (
                        <>
                          <span className="flex-1 text-left">{item.label}</span>
                          {settingsOpen || isSettingsActive ? (
                            <ChevronUp size={14} className="text-[var(--text-secondary)]" />
                          ) : (
                            <ChevronDown size={14} className="text-[var(--text-secondary)]" />
                          )}
                        </>
                      )}
                    </button>

                    {(settingsOpen || isSettingsActive) && !sidebarCollapsed && (
                      <div className="ml-8 mt-1 space-y-0.5 border-l border-[var(--border-color)] pl-3">
                        {item.children.map((child) => {
                          const ChildIcon = ICON_MAP[child.icon];
                          return (
                            <NavLink
                              key={child.path}
                              to={child.path}
                              className={({ isActive }) =>
                                `flex items-center gap-2 rounded-md px-2 py-1.5 text-xs transition-colors duration-150 ${
                                  isActive
                                    ? 'text-[var(--accent-blue)]'
                                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                                }`
                              }
                            >
                              {ChildIcon && <ChildIcon size={14} />}
                              {child.label}
                            </NavLink>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              }

              // Regular nav item
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === '/app'}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors duration-150 ${
                      isActive
                        ? 'bg-[var(--bg-tertiary)] text-[var(--accent-blue)]'
                        : 'text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]'
                    }`
                  }
                >
                  <span className="flex w-5 justify-center">
                    <Icon size={18} />
                  </span>
                  {!sidebarCollapsed && <span>{item.label}</span>}
                </NavLink>
              );
            })}
          </nav>

          {/* Feature filter (contextual — only when chart is active, sits right after nav) */}
          {chartActive && !sidebarCollapsed && (
            <div className="border-t border-[var(--border-color)] px-3 py-3">
              <FeatureFilter
                selectedFeatures={selectedFeatures}
                availableFeatures={featureNames}
                onFeatureToggle={onFeatureToggle}
              />
            </div>
          )}
        </div>

        {/* User info */}
        <div className="border-t border-[var(--border-color)] px-3 py-3">
          {sidebarCollapsed ? (
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--accent-blue)] text-xs font-bold text-white" title={MOCK_USER.name}>
              {MOCK_USER.name.charAt(0)}
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[var(--accent-blue)] text-xs font-bold text-white">
                {MOCK_USER.name.charAt(0)}
              </div>
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{MOCK_USER.name}</div>
                <div className="truncate text-xs text-[var(--text-secondary)]">{MOCK_USER.email}</div>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* Right side: topbar + content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-[var(--border-color)] bg-[var(--bg-secondary)] px-6">
          <Breadcrumbs />

          <div className="flex items-center gap-4">
            {/* Search */}
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
              <input
                type="text"
                placeholder="Search trades..."
                className="h-8 w-56 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] pl-8 pr-3 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
              />
            </div>

            {/* Notification bell */}
            <button
              className="flex h-8 w-8 items-center justify-center rounded-md text-[var(--text-secondary)] transition-colors duration-150 hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
              title="Notifications"
            >
              <Bell size={18} />
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
