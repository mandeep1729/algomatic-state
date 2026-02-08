/**
 * Reusable DataTable component with column visibility persistence and filtering.
 *
 * Features:
 * - Configurable columns with custom renderers
 * - Column visibility toggle with user preference persistence
 * - Per-column text filtering with debounced updates
 * - Loading and empty states
 * - Clickable rows with navigation support
 */

import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { Settings2, X } from 'lucide-react';
import api from '../api';

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
  /** Whether this column is searchable (defaults to true) */
  searchable?: boolean;
  /** Custom filter function. Returns true if the row matches the filter text. */
  filterFn?: (row: T, filterText: string) => boolean;
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

  // Column filter state: maps column key to filter text
  const [columnFilters, setColumnFilters] = useState<Record<string, string>>({});
  // Debounced filter values for performance
  const [debouncedFilters, setDebouncedFilters] = useState<Record<string, string>>({});
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load preferences from API on mount
  useEffect(() => {
    let cancelled = false;

    async function loadPrefs() {
      try {
        const prefs = await api.fetchSitePrefs();
        if (cancelled) return;

        const savedColumns = prefs.table_columns?.[tableName];
        if (savedColumns && Array.isArray(savedColumns) && savedColumns.length > 0) {
          // Filter saved columns to only include keys that exist in current columns definition
          const validColumnKeys = new Set(columns.map((c) => c.key));
          const validSavedColumns = savedColumns.filter((key) => validColumnKeys.has(key));
          if (validSavedColumns.length > 0) {
            setVisibleColumns(new Set(validSavedColumns));
          }
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
  }, [tableName, columns]);

  // Save preferences when columns change (after initial load)
  const savePrefs = useCallback(
    async (cols: Set<string>) => {
      if (!prefsLoaded) return;

      try {
        await api.updateSitePrefs({
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

  // Debounce filter updates (300ms delay)
  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = setTimeout(() => {
      setDebouncedFilters(columnFilters);
    }, 300);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [columnFilters]);

  // Update filter for a column
  const updateFilter = useCallback((columnKey: string, value: string) => {
    setColumnFilters((prev) => {
      if (value === '') {
        const next = { ...prev };
        delete next[columnKey];
        return next;
      }
      return { ...prev, [columnKey]: value };
    });
  }, []);

  // Clear all filters
  const clearAllFilters = useCallback(() => {
    setColumnFilters({});
    setDebouncedFilters({});
  }, []);

  // Check if any filters are active
  const hasActiveFilters = Object.keys(debouncedFilters).length > 0;

  // Filter to only visible columns
  const displayColumns = columns.filter((c) => visibleColumns.has(c.key));
  const hideableColumns = columns.filter((c) => c.hideable !== false);

  // Check if any visible column is searchable
  const hasSearchableColumns = displayColumns.some((c) => c.searchable !== false);

  // Default filter function: case-insensitive partial match on stringified row[key]
  const defaultFilterFn = useCallback(
    (row: T, filterText: string, columnKey: string): boolean => {
      const value = (row as Record<string, unknown>)[columnKey];
      if (value === null || value === undefined) return false;
      const stringValue = String(value).toLowerCase();
      return stringValue.includes(filterText.toLowerCase());
    },
    []
  );

  // Filter data based on all active column filters
  const filteredData = useMemo(() => {
    if (!hasActiveFilters) return data;

    return data.filter((row) => {
      // All filters must match (AND logic)
      for (const [columnKey, filterText] of Object.entries(debouncedFilters)) {
        if (!filterText) continue;

        const column = columns.find((c) => c.key === columnKey);
        if (!column) continue;

        // Use custom filter function if provided, otherwise use default
        const matches = column.filterFn
          ? column.filterFn(row, filterText)
          : defaultFilterFn(row, filterText, columnKey);

        if (!matches) return false;
      }
      return true;
    });
  }, [data, debouncedFilters, hasActiveFilters, columns, defaultFilterFn]);

  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]">
      {/* Header with column visibility toggle and clear filters */}
      <div className="flex items-center justify-end gap-2 border-b border-[var(--border-color)] px-4 py-2">
        {hasActiveFilters && (
          <button
            type="button"
            onClick={clearAllFilters}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] transition-colors"
            aria-label="Clear all filters"
          >
            <X size={14} />
            <span>Clear filters</span>
          </button>
        )}
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
              <th key={col.key} className="px-6 py-3">
                {col.header}
              </th>
            ))}
          </tr>
          {/* Filter row - only show if there are searchable columns */}
          {hasSearchableColumns && (
            <tr className="border-b border-[var(--border-color)] bg-[var(--bg-primary)]/50">
              {displayColumns.map((col) => (
                <th key={`filter-${col.key}`} className="px-6 py-2">
                  {col.searchable !== false ? (
                    <input
                      type="text"
                      value={columnFilters[col.key] || ''}
                      onChange={(e) => updateFilter(col.key, e.target.value)}
                      placeholder="Filter..."
                      className="h-7 w-full max-w-[200px] rounded border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 text-xs font-normal normal-case text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
                    />
                  ) : null}
                </th>
              ))}
            </tr>
          )}
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
          ) : filteredData.length === 0 ? (
            <tr>
              <td
                colSpan={displayColumns.length || 1}
                className="px-6 py-12 text-center text-[var(--text-secondary)]"
              >
                {hasActiveFilters
                  ? 'No rows match the current filters.'
                  : emptyMessage}
              </td>
            </tr>
          ) : (
            filteredData.map((row) => (
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
