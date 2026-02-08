/**
 * Reusable DataTable component with column visibility persistence.
 *
 * Features:
 * - Configurable columns with custom renderers
 * - Column visibility toggle with user preference persistence
 * - Loading and empty states
 * - Clickable rows with navigation support
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { Settings2 } from 'lucide-react';
import { fetchSitePrefs, updateSitePrefs } from '../api/client';

export interface Column<T> {
  /** Unique key for this column */
  key: string;
  /** Display header text */
  header: string;
  /** Custom cell renderer. Receives the row data and returns JSX. */
  render: (row: T) => React.ReactNode;
  /** Whether this column is visible by default (defaults to true) */
  defaultVisible?: boolean;
  /** Whether this column can be hidden (defaults to true) */
  hideable?: boolean;
}

export interface DataTableProps<T> {
  /** Unique identifier for this table (used for preference persistence) */
  tableName: string;
  /** Column definitions */
  columns: Column<T>[];
  /** Data rows */
  data: T[];
  /** Whether data is loading */
  loading?: boolean;
  /** Message to show when data is empty */
  emptyMessage?: string;
  /** Function to get unique key for each row */
  getRowKey: (row: T) => string;
  /** Optional click handler for row clicks */
  onRowClick?: (row: T) => void;
}

export function DataTable<T>({
  tableName,
  columns,
  data,
  loading = false,
  emptyMessage = 'No data available.',
  getRowKey,
  onRowClick,
}: DataTableProps<T>) {
  // Track visible columns by key
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(() => {
    return new Set(columns.filter((c) => c.defaultVisible !== false).map((c) => c.key));
  });
  const [showColumnMenu, setShowColumnMenu] = useState(false);
  const [prefsLoaded, setPrefsLoaded] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Load preferences from API on mount
  useEffect(() => {
    let cancelled = false;

    async function loadPrefs() {
      try {
        const prefs = await fetchSitePrefs();
        if (cancelled) return;

        const savedColumns = prefs.table_columns?.[tableName];
        if (savedColumns && Array.isArray(savedColumns) && savedColumns.length > 0) {
          // Use saved preferences
          setVisibleColumns(new Set(savedColumns));
        }
      } catch {
        // Preferences not available, use defaults
      } finally {
        if (!cancelled) setPrefsLoaded(true);
      }
    }

    loadPrefs();
    return () => {
      cancelled = true;
    };
  }, [tableName]);

  // Save preferences when columns change (after initial load)
  const savePrefs = useCallback(
    async (cols: Set<string>) => {
      if (!prefsLoaded) return;

      try {
        await updateSitePrefs({
          table_columns: {
            [tableName]: Array.from(cols),
          },
        });
      } catch {
        // Failed to save preferences, continue silently
      }
    },
    [tableName, prefsLoaded]
  );

  // Toggle column visibility
  const toggleColumn = useCallback(
    (key: string) => {
      setVisibleColumns((prev) => {
        const next = new Set(prev);
        if (next.has(key)) {
          next.delete(key);
        } else {
          next.add(key);
        }
        savePrefs(next);
        return next;
      });
    },
    [savePrefs]
  );

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowColumnMenu(false);
      }
    }

    if (showColumnMenu) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showColumnMenu]);

  // Filter to only visible columns
  const displayColumns = columns.filter((c) => visibleColumns.has(c.key));
  const hideableColumns = columns.filter((c) => c.hideable !== false);

  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]">
      {/* Header with column visibility toggle */}
      <div className="flex items-center justify-end border-b border-[var(--border-color)] px-4 py-2">
        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => setShowColumnMenu(!showColumnMenu)}
            className="flex items-center gap-1.5 rounded px-2 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] transition-colors"
            aria-label="Toggle column visibility"
          >
            <Settings2 size={14} />
            <span>Columns</span>
          </button>

          {showColumnMenu && (
            <div className="absolute right-0 top-full z-10 mt-1 min-w-[160px] rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] py-1 shadow-lg">
              {hideableColumns.map((col) => (
                <label
                  key={col.key}
                  className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-xs hover:bg-[var(--bg-tertiary)]"
                >
                  <input
                    type="checkbox"
                    checked={visibleColumns.has(col.key)}
                    onChange={() => toggleColumn(col.key)}
                    className="h-3.5 w-3.5 rounded border-[var(--border-color)] text-[var(--accent-blue)] focus:ring-[var(--accent-blue)]"
                  />
                  <span className="text-[var(--text-primary)]">{col.header}</span>
                </label>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Table */}
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border-color)] text-left text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
            {displayColumns.map((col) => (
              <th key={col.key} className="px-6 py-4">
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border-color)]">
          {loading ? (
            <tr>
              <td
                colSpan={displayColumns.length || 1}
                className="px-6 py-12 text-center text-[var(--text-secondary)]"
              >
                Loading...
              </td>
            </tr>
          ) : data.length === 0 ? (
            <tr>
              <td
                colSpan={displayColumns.length || 1}
                className="px-6 py-12 text-center text-[var(--text-secondary)]"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row) => (
              <tr
                key={getRowKey(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={
                  onRowClick
                    ? 'cursor-pointer transition-colors hover:bg-[var(--bg-tertiary)]/50'
                    : ''
                }
              >
                {displayColumns.map((col) => (
                  <td key={col.key} className="px-6 py-4">
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
