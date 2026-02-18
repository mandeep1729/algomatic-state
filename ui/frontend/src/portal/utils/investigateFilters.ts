/**
 * Filter logic for the Investigate page.
 *
 * FilterChip describes a single filter criterion applied to campaigns.
 * applyFilters reduces a campaign list to only those matching all chips.
 */

import type { CampaignSummary } from '../types';

export type FilterField =
  | 'symbol'
  | 'strategy'
  | 'direction'
  | 'status'
  | 'flag'
  | 'dateRange'
  | 'pnlRange';

export type FilterOp = 'eq' | 'in' | 'gte' | 'lte' | 'between';

export interface FilterChip {
  id: string;
  field: FilterField;
  op: FilterOp;
  value: string | string[] | number | [number, number];
  label: string;
  source: 'manual' | 'chart-click';
}

let chipCounter = 0;

/** Create a new filter chip with a unique id. */
export function createChip(
  field: FilterField,
  op: FilterOp,
  value: FilterChip['value'],
  label: string,
  source: FilterChip['source'] = 'manual',
): FilterChip {
  return { id: `chip-${++chipCounter}`, field, op, value, label, source };
}

/** Check if a single campaign matches a single chip. */
function matchesChip(c: CampaignSummary, chip: FilterChip): boolean {
  switch (chip.field) {
    case 'symbol':
      return chip.op === 'eq'
        ? c.symbol === chip.value
        : chip.op === 'in'
          ? (chip.value as string[]).includes(c.symbol)
          : false;

    case 'direction':
      return c.direction === chip.value;

    case 'status':
      return c.status === chip.value;

    case 'strategy':
      if (chip.op === 'eq') return c.strategies.includes(chip.value as string);
      if (chip.op === 'in') return (chip.value as string[]).some((s) => c.strategies.includes(s));
      return false;

    case 'flag':
      if (chip.op === 'eq') return c.keyFlags.includes(chip.value as string);
      if (chip.op === 'in') return (chip.value as string[]).some((f) => c.keyFlags.includes(f));
      return false;

    case 'pnlRange': {
      const pnl = c.pnlRealized ?? 0;
      if (chip.op === 'gte') return pnl >= (chip.value as number);
      if (chip.op === 'lte') return pnl <= (chip.value as number);
      if (chip.op === 'between') {
        const [lo, hi] = chip.value as [number, number];
        return pnl >= lo && pnl <= hi;
      }
      return false;
    }

    case 'dateRange': {
      const opened = new Date(c.openedAt).getTime();
      if (chip.op === 'gte') return opened >= new Date(chip.value as string).getTime();
      if (chip.op === 'lte') return opened <= new Date(chip.value as string).getTime();
      if (chip.op === 'between') {
        const [start, end] = chip.value as [string, string];
        return opened >= new Date(start).getTime() && opened <= new Date(end).getTime();
      }
      return false;
    }

    default:
      return true;
  }
}

/** Apply all filter chips (AND logic) to a list of campaigns. */
export function applyFilters(
  campaigns: CampaignSummary[],
  chips: FilterChip[],
): CampaignSummary[] {
  if (chips.length === 0) return campaigns;
  return campaigns.filter((c) => chips.every((chip) => matchesChip(c, chip)));
}
