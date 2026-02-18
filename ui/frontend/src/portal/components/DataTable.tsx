/**
 * Reusable DataTable component with column visibility persistence and filtering.
 *
 * Features:
 * - Configurable columns with custom renderers
 * - Column visibility toggle with user preference persistence
 * - Per-column text filtering with debounced updates
 * - Pagination with configurable rows-per-page selector
 * - Loading and empty states
 * - Clickable rows with navigation support
 */

import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { Settings2, X, ChevronRight } from 'lucide-react';
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

/** Available page size options for the rows-per-page selector */
const ROWS_PER_PAGE_OPTIONS = [5, 10, 25, 50, 100] as const;

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
  /** Set of selected row keys. When provided, a checkbox column is rendered. */
  selectedKeys?: Set<string>;
  /** Callback when selection changes. Required when selectedKeys is provided. */
  onSelectionChange?: (keys: Set<string>) => void;
  /** Optional callback when rows-per-page changes, for parent to sync if needed */
  onRowsPerPageChange?: (rowsPerPage: number) => void;
  /** Set of expanded row keys. When provided with onExpandChange and renderExpandedRow, enables expandable rows. */
  expandedKeys?: Set<string>;
  /** Callback when expansion changes. Required when expandedKeys is provided. */
  onExpandChange?: (keys: Set<string>) => void;
  /** Render function for expanded row content. Required when expandedKeys is provided. */
  renderExpandedRow?: (row: T) => React.ReactNode;
}

export function DataTable<T>({
  tableName,
  columns,
  data,
  loading = false,
  emptyMessage = 'No data available.',
  getRowKey,
  onRowClick,
  selectedKeys,
  onSelectionChange,
  onRowsPerPageChange,
  expandedKeys,
  onExpandChange,
  renderExpandedRow,
}: DataTableProps<T>) {
  const selectionEnabled = selectedKeys !== undefined && onSelectionChange !== undefined;
  const expansionEnabled = expandedKeys !== undefined && onExpandChange !== undefined && renderExpandedRow !== undefined;

  // Pagination state
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [currentPage, setCurrentPage] = useState(0);
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

  // Selection helpers
  const toggleRowSelection = useCallback(
    (key: string) => {
      if (!selectionEnabled) return;
      const next = new Set(selectedKeys);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      onSelectionChange!(next);
    },
    [selectionEnabled, selectedKeys, onSelectionChange],
  );

  const toggleSelectAll = useCallback(
    (filteredRows: T[]) => {
      if (!selectionEnabled) return;
      const allKeys = filteredRows.map(getRowKey);
      const allSelected = allKeys.length > 0 && allKeys.every((k) => selectedKeys!.has(k));
      if (allSelected) {
        // Deselect all currently visible rows
        const next = new Set(selectedKeys);
        for (const k of allKeys) next.delete(k);
        onSelectionChange!(next);
      } else {
        // Select all currently visible rows
        const next = new Set(selectedKeys);
        for (const k of allKeys) next.add(k);
        onSelectionChange!(next);
      }
    },
    [selectionEnabled, selectedKeys, onSelectionChange, getRowKey],
  );

  // Toggle row expansion
  const toggleRowExpansion = useCallback(
    (key: string) => {
      if (!expansionEnabled) return;
      const next = new Set(expandedKeys);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      onExpandChange!(next);
    },
    [expansionEnabled, expandedKeys, onExpandChange],
  );

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

  // Reset currentPage when filteredData length changes (e.g. filters applied)
  const prevFilteredLengthRef = useRef(filteredData.length);
  useEffect(() => {
    if (filteredData.length !== prevFilteredLengthRef.current) {
      prevFilteredLengthRef.current = filteredData.length;
      setCurrentPage(0);
    }
  }, [filteredData.length]);

  // Pagination calculations
  const totalPages = Math.max(1, Math.ceil(filteredData.length / rowsPerPage));
  const safeCurrentPage = Math.min(currentPage, totalPages - 1);
  const paginatedData = useMemo(() => {
    const start = safeCurrentPage * rowsPerPage;
    return filteredData.slice(start, start + rowsPerPage);
  }, [filteredData, safeCurrentPage, rowsPerPage]);

  // Handler for rows-per-page change
  const handleRowsPerPageChange = useCallback(
    (newRowsPerPage: number) => {
      setRowsPerPage(newRowsPerPage);
      setCurrentPage(0);
      onRowsPerPageChange?.(newRowsPerPage);
    },
    [onRowsPerPageChange]
  );

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
            {expansionEnabled && <th className="w-8 px-1 py-3" />}
            {selectionEnabled && (
              <th className="w-10 px-3 py-3">
                <input
                  type="checkbox"
                  checked={
                    filteredData.length > 0 &&
                    filteredData.every((row) => selectedKeys!.has(getRowKey(row)))
                  }
                  onChange={() => toggleSelectAll(filteredData)}
                  className="h-3.5 w-3.5 rounded border-[var(--border-color)] text-[var(--accent-blue)] focus:ring-[var(--accent-blue)]"
                  aria-label="Select all rows"
                />
              </th>
            )}
            {displayColumns.map((col) => (
              <th key={col.key} className="px-6 py-3">
                {col.header}
              </th>
            ))}
          </tr>
          {/* Filter row - only show if there are searchable columns */}
          {hasSearchableColumns && (
            <tr className="border-b border-[var(--border-color)] bg-[var(--bg-primary)]/50">
              {expansionEnabled && <th className="w-8 px-1 py-2" />}
              {selectionEnabled && <th className="w-10 px-3 py-2" />}
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
                colSpan={(displayColumns.length || 1) + (selectionEnabled ? 1 : 0) + (expansionEnabled ? 1 : 0)}
                className="px-6 py-12 text-center text-[var(--text-secondary)]"
              >
                Loading...
              </td>
            </tr>
          ) : filteredData.length === 0 ? (
            <tr>
              <td
                colSpan={(displayColumns.length || 1) + (selectionEnabled ? 1 : 0) + (expansionEnabled ? 1 : 0)}
                className="px-6 py-12 text-center text-[var(--text-secondary)]"
              >
                {hasActiveFilters
                  ? 'No rows match the current filters.'
                  : emptyMessage}
              </td>
            </tr>
          ) : (
            paginatedData.map((row) => {
              const rowKey = getRowKey(row);
              const isSelected = selectionEnabled && selectedKeys!.has(rowKey);
              const isExpanded = expansionEnabled && expandedKeys!.has(rowKey);
              return (
                <React.Fragment key={rowKey}>
                  <tr
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    className={`${
                      onRowClick
                        ? 'cursor-pointer transition-colors hover:bg-[var(--bg-tertiary)]/50'
                        : 'transition-colors'
                    } ${isSelected ? 'bg-[var(--accent-blue)]/5' : ''}`}
                  >
                    {expansionEnabled && (
                      <td className="w-8 px-1 py-4">
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); toggleRowExpansion(rowKey); }}
                          className="flex items-center justify-center rounded p-0.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-all"
                          aria-label={isExpanded ? 'Collapse row' : 'Expand row'}
                        >
                          <ChevronRight
                            size={16}
                            className={`transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`}
                          />
                        </button>
                      </td>
                    )}
                    {selectionEnabled && (
                      <td className="w-10 px-3 py-4">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleRowSelection(rowKey)}
                          onClick={(e) => e.stopPropagation()}
                          className="h-3.5 w-3.5 rounded border-[var(--border-color)] text-[var(--accent-blue)] focus:ring-[var(--accent-blue)]"
                          aria-label={`Select row ${rowKey}`}
                        />
                      </td>
                    )}
                    {displayColumns.map((col) => (
                      <td key={col.key} className="px-6 py-4">
                        {col.render(row)}
                      </td>
                    ))}
                  </tr>
                  {isExpanded && (
                    <tr className="bg-[var(--bg-primary)]/50">
                      <td colSpan={(displayColumns.length || 1) + (selectionEnabled ? 1 : 0) + (expansionEnabled ? 1 : 0)}>
                        {renderExpandedRow!(row)}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })
          )}
        </tbody>
      </table>

      {/* Pagination footer */}
      {filteredData.length > 0 && (
        <div className="flex items-center justify-between border-t border-[var(--border-color)] px-4 py-2">
          <span className="text-xs text-[var(--text-secondary)]">
            {hasActiveFilters
              ? `Showing ${filteredData.length} of ${data.length} ${data.length === 1 ? 'result' : 'results'}`
              : `${data.length} ${data.length === 1 ? 'row' : 'rows'}`}
          </span>
          <div className="flex items-center gap-3">
            {/* Rows per page selector */}
            <div className="flex items-center gap-1.5">
              <label
                htmlFor={`${tableName}-rows-per-page`}
                className="text-xs text-[var(--text-secondary)]"
              >
                Rows per page:
              </label>
              <select
                id={`${tableName}-rows-per-page`}
                value={rowsPerPage}
                onChange={(e) => handleRowsPerPageChange(Number(e.target.value))}
                className="h-7 rounded border border-[var(--border-color)] bg-[var(--bg-primary)] px-1.5 text-xs text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] focus:border-[var(--accent-blue)] focus:outline-none transition-colors"
              >
                {ROWS_PER_PAGE_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            </div>

            {/* Page indicator */}
            <span className="text-xs text-[var(--text-secondary)]">
              Page {safeCurrentPage + 1} of {totalPages}
            </span>

            {/* Previous / Next buttons */}
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
                disabled={safeCurrentPage === 0}
                className="rounded border border-[var(--border-color)] bg-[var(--bg-primary)] px-2.5 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                aria-label="Previous page"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={safeCurrentPage >= totalPages - 1}
                className="rounded border border-[var(--border-color)] bg-[var(--bg-primary)] px-2.5 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                aria-label="Next page"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
