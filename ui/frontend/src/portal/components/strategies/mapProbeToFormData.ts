/**
 * Shared utility to map a ThemeStrategyDetail (probe strategy) to
 * Partial<StrategyDefinition> suitable for the clone-from-existing
 * dropdown in StrategyForm.
 */

import type { ThemeStrategyDetail } from '../../api/client';
import type { StrategyCategory, StrategyDefinition } from '../../types';

/**
 * Known probe strategy_type values that map directly to StrategyCategory.
 * Any unrecognised type falls back to 'custom'.
 */
const STRATEGY_TYPE_TO_CATEGORY: Record<string, StrategyCategory> = {
  trend: 'trend',
  mean_reversion: 'mean_reversion',
  breakout: 'breakout',
  volume_flow: 'volume_flow',
  pattern: 'pattern',
  regime: 'regime',
  momentum: 'custom',
  volatility: 'custom',
};

function resolveCategory(strategyType?: string): StrategyCategory {
  if (!strategyType) return 'custom';
  return STRATEGY_TYPE_TO_CATEGORY[strategyType] ?? 'custom';
}

function resolveDirection(direction: string): StrategyDefinition['direction'] {
  if (direction === 'long_short') return 'long_short';
  if (direction === 'long_only') return 'long_only';
  if (direction === 'short_only') return 'short_only';
  return 'long_short';
}

export function mapProbeToFormData(s: ThemeStrategyDetail): Partial<StrategyDefinition> {
  const details = s.details || {};

  return {
    name: s.name,
    display_name: s.display_name,
    description: s.philosophy,
    category: resolveCategory(s.strategy_type),
    direction: resolveDirection(s.direction),
    entry_long: typeof details.entry_long === 'string' ? details.entry_long : null,
    entry_short: typeof details.entry_short === 'string' ? details.entry_short : null,
    exit_long: typeof details.exit === 'string' ? details.exit : null,
    required_features: Array.isArray(details.indicators) ? details.indicators as string[] : null,
    tags: Array.isArray(details.tags) ? details.tags as string[] : null,
  };
}
