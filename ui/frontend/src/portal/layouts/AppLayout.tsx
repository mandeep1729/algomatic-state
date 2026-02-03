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
    <div className="flex h-screen w-full overflow-hidden bg-[var(--bg-primary)] text-[var(--text-primary)] font-sans antialiased text-sm">
      {/* Sidebar */}
      <aside
        className={`relative flex flex-shrink-0 flex-col border-r border-[var(--border-color)] bg-[var(--bg-primary)] transition-all duration-300 ease-in-out ${sidebarCollapsed ? 'w-[72px]' : 'w-64'
          }`}
      >
        {/* Logo / brand */}
        <div className={`flex h-16 items-center border-b border-[var(--border-color)] ${sidebarCollapsed ? 'justify-center' : 'justify-between px-6'}`}>
          {!sidebarCollapsed && (
            <div className="flex items-center gap-2 font-semibold tracking-tight text-base">
              <div className="flex h-6 w-6 items-center justify-center rounded bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]">
                <Shield size={14} />
              </div>
              Trading Buddy
            </div>
          )}
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="flex h-6 w-6 items-center justify-center rounded-md text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {sidebarCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
          </button>
        </div>

        {/* Nav + Feature Filter (shared scrollable area) */}
        <div className="flex-1 overflow-y-auto py-4">
          <nav className="space-y-1 px-3">
            {appNavSections.map((item) => {
              const Icon = ICON_MAP[item.icon] ?? LayoutDashboard;

              // Settings with sub-nav
              if (item.children) {
                return (
                  <div key={item.path} className="group">
                    <button
                      onClick={() => setSettingsOpen(!settingsOpen)}
                      className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${isSettingsActive
                        ? 'bg-[var(--bg-tertiary)]/50 text-[var(--text-primary)]'
                        : 'text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]/30 hover:text-[var(--text-primary)]'
                        } ${sidebarCollapsed ? 'justify-center px-2' : ''}`}
                    >
                      <span className="flex items-center justify-center">
                        <Icon size={18} />
                      </span>
                      {!sidebarCollapsed && (
                        <>
                          <span className="flex-1 text-left">{item.label}</span>
                          <ChevronDown
                            size={14}
                            className={`transform transition-transform text-[var(--text-secondary)] ${settingsOpen || isSettingsActive ? 'rotate-180' : ''
                              }`}
                          />
                        </>
                      )}
                    </button>

                    {(settingsOpen || isSettingsActive) && !sidebarCollapsed && (
                      <div className="mt-1 space-y-0.5 pl-9 pr-2">
                        {item.children.map((child) => {
                          const ChildIcon = ICON_MAP[child.icon];
                          return (
                            <NavLink
                              key={child.path}
                              to={child.path}
                              className={({ isActive }) =>
                                `flex items-center gap-2 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${isActive
                                  ? 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
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
                    `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${isActive
                      ? 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                      : 'text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]/30 hover:text-[var(--text-primary)]'
                    } ${sidebarCollapsed ? 'justify-center px-2' : ''}`
                  }
                  title={sidebarCollapsed ? item.label : undefined}
                >
                  <span className="flex items-center justify-center">
                    <Icon size={18} />
                  </span>
                  {!sidebarCollapsed && <span>{item.label}</span>}
                </NavLink>
              );
            })}
          </nav>

          {/* Feature filter (contextual — only when chart is active, sits right after nav) */}
          {chartActive && !sidebarCollapsed && (
            <div className="mt-6 border-t border-[var(--border-color)] px-4 py-4">
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Chart Features</h3>
              <FeatureFilter
                selectedFeatures={selectedFeatures}
                availableFeatures={featureNames}
                onFeatureToggle={onFeatureToggle}
              />
            </div>
          )}
        </div>

        {/* User info */}
        <div className="border-t border-[var(--border-color)] p-4">
          {sidebarCollapsed ? (
            <div className="flex justify-center">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-[var(--accent-blue)] to-[var(--accent-purple)] text-xs font-bold text-white shadow-md">
                {MOCK_USER.name.charAt(0)}
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3 rounded-lg border border-transparent p-2 transition-colors hover:border-[var(--border-color)] hover:bg-[var(--bg-secondary)]">
              <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[var(--accent-blue)] to-[var(--accent-purple)] text-xs font-bold text-white shadow-sm">
                {MOCK_USER.name.charAt(0)}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-[var(--text-primary)]">{MOCK_USER.name}</div>
                <div className="truncate text-xs text-[var(--text-secondary)]">{MOCK_USER.email}</div>
              </div>
              <Settings size={14} className="text-[var(--text-secondary)]" />
            </div>
          )}
        </div>
      </aside>

      {/* Right side: topbar + content */}
      <div className="flex flex-1 flex-col overflow-hidden bg-[var(--bg-primary)]">
        {/* Top bar */}
        <header className="flex h-16 flex-shrink-0 items-center justify-between border-b border-[var(--border-color)] bg-[var(--bg-primary)] px-8">
          <Breadcrumbs />

          <div className="flex items-center gap-4">
            {/* Search */}
            <div className="relative group">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-secondary)] transition-colors group-focus-within:text-[var(--accent-blue)]" />
              <input
                type="text"
                placeholder="Search..."
                className="h-9 w-64 rounded-full border border-[var(--border-color)] bg-[var(--bg-secondary)]/50 pl-9 pr-4 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] transition-all focus:w-72 focus:border-[var(--accent-blue)] focus:bg-[var(--bg-secondary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-blue)]"
              />
            </div>

            <div className="h-6 w-px bg-[var(--border-color)]"></div>

            {/* Notification bell */}
            <button
              className="relative flex h-9 w-9 items-center justify-center rounded-full text-[var(--text-secondary)] transition-all hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
              title="Notifications"
            >
              <Bell size={18} />
              <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-[var(--accent-red)] ring-2 ring-[var(--bg-primary)]"></span>
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto bg-[var(--bg-secondary)]/30 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-[var(--border-color)]">
          <div className="mx-auto max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
