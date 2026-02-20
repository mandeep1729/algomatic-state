/**
 * Default family strategies available to all users.
 * These are combined with user-defined strategies in strategy selection dropdowns.
 */

export const DEFAULT_STRATEGIES = [
  'trend family',
  'breakout family',
  'volume flow family',
  'mean-reversion family',
  'regime family',
  'pattern family',
];

/**
 * Merge user-defined strategies with default family strategies.
 * Deduplicates by name (case-insensitive).
 * User strategies take precedence if there's a name match.
 */
export function mergeStrategies(
  userStrategies: Array<{ id: string | number; name: string }>,
  includeDefaults: boolean = true,
): Array<{ id: string; name: string; isDefault?: boolean }> {
  const merged = new Map<string, { id: string; name: string; isDefault?: boolean }>();

  // Add user strategies first (they take precedence)
  for (const strategy of userStrategies) {
    const key = strategy.name.toLowerCase();
    merged.set(key, { id: String(strategy.id), name: strategy.name });
  }

  // Add default strategies if they don't exist
  if (includeDefaults) {
    for (const defaultName of DEFAULT_STRATEGIES) {
      const key = defaultName.toLowerCase();
      if (!merged.has(key)) {
        merged.set(key, {
          id: defaultName,
          name: defaultName,
          isDefault: true,
        });
      }
    }
  }

  // Return as array, sorted by name
  return Array.from(merged.values()).sort((a, b) =>
    a.name.localeCompare(b.name),
  );
}
