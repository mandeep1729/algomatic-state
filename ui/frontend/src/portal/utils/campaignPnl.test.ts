import { describe, it, expect } from 'vitest';
import { computeCampaignRunningPnl } from './campaignPnl';
import type { CampaignLeg } from '../types';

/** Helper to build a minimal CampaignLeg for testing. */
function makeLeg(
  overrides: Partial<CampaignLeg> & Pick<CampaignLeg, 'legType' | 'side' | 'quantity' | 'avgPrice' | 'startedAt'>,
): CampaignLeg {
  return {
    legId: '1',
    campaignId: '1',
    endedAt: overrides.startedAt,
    ...overrides,
  };
}

/**
 * Generate hourly OHLCV timestamps starting from a given ISO string.
 * Returns timestamps and uniform close prices.
 */
function makeOhlcv(startIso: string, count: number, closePrice: number) {
  const startMs = new Date(startIso).getTime();
  const timestamps: string[] = [];
  const closes: number[] = [];
  for (let i = 0; i < count; i++) {
    timestamps.push(new Date(startMs + i * 3600_000).toISOString());
    closes.push(closePrice);
  }
  return { timestamps, closes };
}

describe('computeCampaignRunningPnl', () => {
  // ─── LONG CAMPAIGNS ────────────────────────────────────────────────

  it('long: simple open then close with profit', () => {
    const legs: CampaignLeg[] = [
      makeLeg({ legType: 'open', side: 'buy', quantity: 10, avgPrice: 100, startedAt: '2026-01-01T10:00:00Z' }),
      makeLeg({ legId: '2', legType: 'close', side: 'sell', quantity: 10, avgPrice: 110, startedAt: '2026-01-01T14:00:00Z' }),
    ];
    const { timestamps } = makeOhlcv('2026-01-01T09:00:00Z', 8, 105);
    // Override close prices to show price progression
    const prices = [95, 100, 102, 105, 108, 110, 112, 112];

    const pnl = computeCampaignRunningPnl(legs, 'long', timestamps, prices);

    // Before open (T09): no position → PnL = 0
    expect(pnl[0]).toBe(0);
    // After open at T10 (index 1): qty=10, cost=100, close=100 → unrealized = (100-100)*10 = 0
    expect(pnl[1]).toBe(0);
    // T11 (index 2): close=102 → unrealized = (102-100)*10 = 20
    expect(pnl[2]).toBe(20);
    // T12 (index 3): close=105 → unrealized = (105-100)*10 = 50
    expect(pnl[3]).toBe(50);
    // T13 (index 4): close=108 → unrealized = (108-100)*10 = 80
    expect(pnl[4]).toBe(80);
    // After close at T14 (index 5): realized = (110-100)*10 = 100, no position
    expect(pnl[5]).toBe(100);
    // After close, PnL stays at realized
    expect(pnl[6]).toBe(100);
    expect(pnl[7]).toBe(100);
  });

  it('long: simple open then close with loss', () => {
    const legs: CampaignLeg[] = [
      makeLeg({ legType: 'open', side: 'buy', quantity: 5, avgPrice: 200, startedAt: '2026-01-01T10:00:00Z' }),
      makeLeg({ legId: '2', legType: 'close', side: 'sell', quantity: 5, avgPrice: 180, startedAt: '2026-01-01T12:00:00Z' }),
    ];
    const timestamps = [
      '2026-01-01T10:00:00Z',
      '2026-01-01T11:00:00Z',
      '2026-01-01T12:00:00Z',
    ];
    const prices = [200, 190, 180];

    const pnl = computeCampaignRunningPnl(legs, 'long', timestamps, prices);

    // T10: open at 200, close=200 → unrealized = 0
    expect(pnl[0]).toBe(0);
    // T11: close=190 → unrealized = (190-200)*5 = -50
    expect(pnl[1]).toBe(-50);
    // T12: closed at 180 → realized = (180-200)*5 = -100
    expect(pnl[2]).toBe(-100);
  });

  it('long: open + add then close', () => {
    const legs: CampaignLeg[] = [
      makeLeg({ legType: 'open', side: 'buy', quantity: 10, avgPrice: 100, startedAt: '2026-01-01T10:00:00Z' }),
      makeLeg({ legId: '2', legType: 'add', side: 'buy', quantity: 5, avgPrice: 110, startedAt: '2026-01-01T12:00:00Z' }),
      makeLeg({ legId: '3', legType: 'close', side: 'sell', quantity: 15, avgPrice: 120, startedAt: '2026-01-01T14:00:00Z' }),
    ];
    const timestamps = [
      '2026-01-01T10:00:00Z',
      '2026-01-01T11:00:00Z',
      '2026-01-01T12:00:00Z',
      '2026-01-01T13:00:00Z',
      '2026-01-01T14:00:00Z',
    ];
    const prices = [100, 105, 110, 115, 120];

    const pnl = computeCampaignRunningPnl(legs, 'long', timestamps, prices);

    // T10: open 10@100, close=100 → unrealized=0
    expect(pnl[0]).toBe(0);
    // T11: close=105 → (105-100)*10 = 50
    expect(pnl[1]).toBe(50);
    // T12: add 5@110, total cost=10*100+5*110=1550, qty=15, avg=103.33
    // close=110 → (110-103.333)*15 = 100
    expect(pnl[2]).toBe(100);
    // T13: close=115 → (115-103.333)*15 = 175
    expect(pnl[3]).toBe(175);
    // T14: close all 15@120 → realized = (120-103.333)*15 = 250
    expect(pnl[4]).toBe(250);
  });

  // ─── SHORT CAMPAIGNS ───────────────────────────────────────────────

  it('short: simple open then close with profit', () => {
    // Short sell 10 shares at $100, buy back at $90 → profit $100
    const legs: CampaignLeg[] = [
      makeLeg({ legType: 'open', side: 'sell', quantity: 10, avgPrice: 100, startedAt: '2026-01-01T10:00:00Z' }),
      makeLeg({ legId: '2', legType: 'close', side: 'buy', quantity: 10, avgPrice: 90, startedAt: '2026-01-01T13:00:00Z' }),
    ];
    const timestamps = [
      '2026-01-01T10:00:00Z',
      '2026-01-01T11:00:00Z',
      '2026-01-01T12:00:00Z',
      '2026-01-01T13:00:00Z',
      '2026-01-01T14:00:00Z',
    ];
    const prices = [100, 95, 92, 90, 88];

    const pnl = computeCampaignRunningPnl(legs, 'short', timestamps, prices);

    // T10: open short 10@100, close=100 → unrealized = (100-100)*10*(-1) = 0
    expect(pnl[0]).toBe(0);
    // T11: close=95 → unrealized = (95-100)*10*(-1) = 50
    expect(pnl[1]).toBe(50);
    // T12: close=92 → unrealized = (92-100)*10*(-1) = 80
    expect(pnl[2]).toBe(80);
    // T13: close at 90 → realized = (90-100)*10*(-1) = 100
    expect(pnl[3]).toBe(100);
    // After close, flat → stays at 100
    expect(pnl[4]).toBe(100);
  });

  it('short: simple open then close with loss', () => {
    // Short sell 10 at $100, buy back at $120 → loss $200
    const legs: CampaignLeg[] = [
      makeLeg({ legType: 'open', side: 'sell', quantity: 10, avgPrice: 100, startedAt: '2026-01-01T10:00:00Z' }),
      makeLeg({ legId: '2', legType: 'close', side: 'buy', quantity: 10, avgPrice: 120, startedAt: '2026-01-01T12:00:00Z' }),
    ];
    const timestamps = [
      '2026-01-01T10:00:00Z',
      '2026-01-01T11:00:00Z',
      '2026-01-01T12:00:00Z',
    ];
    const prices = [100, 110, 120];

    const pnl = computeCampaignRunningPnl(legs, 'short', timestamps, prices);

    // T10: open short, close=100 → 0
    expect(pnl[0]).toBe(0);
    // T11: close=110 → unrealized = (110-100)*10*(-1) = -100
    expect(pnl[1]).toBe(-100);
    // T12: close at 120 → realized = (120-100)*10*(-1) = -200
    expect(pnl[2]).toBe(-200);
  });

  it('short: open + add + partial reduce (campaign 25 scenario)', () => {
    // Real campaign 25 data: GOOG short
    const legs: CampaignLeg[] = [
      makeLeg({ legType: 'open', side: 'sell', quantity: 10, avgPrice: 338.821, startedAt: '2026-02-03T19:07:57Z' }),
      makeLeg({ legId: '2', legType: 'add', side: 'sell', quantity: 1, avgPrice: 340.01, startedAt: '2026-02-03T19:13:20Z' }),
      makeLeg({ legId: '3', legType: 'reduce', side: 'buy', quantity: 10, avgPrice: 325.454, startedAt: '2026-02-05T18:23:27Z' }),
    ];
    // Three OHLCV bars: one before add, one after add, one at reduce
    const timestamps = [
      '2026-02-03T19:10:00Z',  // after open, before add
      '2026-02-03T19:15:00Z',  // after add
      '2026-02-05T18:25:00Z',  // after reduce
    ];
    const prices = [339, 339, 325];

    const pnl = computeCampaignRunningPnl(legs, 'short', timestamps, prices);

    // After open: qty=10, avg=338.821, close=339
    // unrealized = (339 - 338.821) * 10 * (-1) = -1.79
    expect(pnl[0]).toBeCloseTo(-1.79, 1);

    // After add: qty=11, cost=10*338.821+1*340.01=3728.22, avg=338.929
    // unrealized = (339 - 338.929) * 11 * (-1) = -0.78
    expect(pnl[1]).toBeCloseTo(-0.78, 0);

    // After reduce 10@325.454: realized = (325.454-338.929)*10*(-1) = 134.75
    // remaining qty=1, avg=338.929, close=325
    // unrealized = (325-338.929)*1*(-1) = 13.93
    // total ≈ 148.68
    expect(pnl[2]).toBeCloseTo(148.68, 0);
  });

  it('short: open-only (still open, no closes)', () => {
    const legs: CampaignLeg[] = [
      makeLeg({ legType: 'open', side: 'sell', quantity: 5, avgPrice: 50, startedAt: '2026-01-01T10:00:00Z' }),
    ];
    const timestamps = [
      '2026-01-01T10:00:00Z',
      '2026-01-01T11:00:00Z',
      '2026-01-01T12:00:00Z',
    ];
    const prices = [50, 48, 45];

    const pnl = computeCampaignRunningPnl(legs, 'short', timestamps, prices);

    // T10: short 5@50, close=50 → unrealized = (50-50)*5*(-1) = 0
    expect(pnl[0]).toBe(0);
    // T11: close=48 → unrealized = (48-50)*5*(-1) = 10
    expect(pnl[1]).toBe(10);
    // T12: close=45 → unrealized = (45-50)*5*(-1) = 25
    expect(pnl[2]).toBe(25);
  });

  // ─── EDGE CASES ────────────────────────────────────────────────────

  it('empty legs returns all zeros', () => {
    const { timestamps, closes } = makeOhlcv('2026-01-01T10:00:00Z', 3, 100);
    const pnl = computeCampaignRunningPnl([], 'long', timestamps, closes);
    expect(pnl).toEqual([0, 0, 0]);
  });

  it('legs after all timestamps produces zeros', () => {
    const legs: CampaignLeg[] = [
      makeLeg({ legType: 'open', side: 'buy', quantity: 10, avgPrice: 100, startedAt: '2026-01-02T10:00:00Z' }),
    ];
    // OHLCV is day before
    const { timestamps, closes } = makeOhlcv('2026-01-01T10:00:00Z', 3, 100);
    const pnl = computeCampaignRunningPnl(legs, 'long', timestamps, closes);
    expect(pnl).toEqual([0, 0, 0]);
  });

  it('long: partial reduce preserves remaining unrealized PnL', () => {
    const legs: CampaignLeg[] = [
      makeLeg({ legType: 'open', side: 'buy', quantity: 20, avgPrice: 100, startedAt: '2026-01-01T10:00:00Z' }),
      makeLeg({ legId: '2', legType: 'reduce', side: 'sell', quantity: 10, avgPrice: 120, startedAt: '2026-01-01T12:00:00Z' }),
    ];
    const timestamps = [
      '2026-01-01T10:00:00Z',
      '2026-01-01T11:00:00Z',
      '2026-01-01T12:00:00Z',
      '2026-01-01T13:00:00Z',
    ];
    const prices = [100, 110, 120, 130];

    const pnl = computeCampaignRunningPnl(legs, 'long', timestamps, prices);

    // T10: 20@100, close=100 → 0
    expect(pnl[0]).toBe(0);
    // T11: close=110 → (110-100)*20 = 200
    expect(pnl[1]).toBe(200);
    // T12: sell 10@120, realized = (120-100)*10 = 200
    // remaining 10@100, close=120 → unrealized = (120-100)*10 = 200
    // total = 400
    expect(pnl[2]).toBe(400);
    // T13: realized=200, remaining 10@100, close=130 → unrealized = 300
    // total = 500
    expect(pnl[3]).toBe(500);
  });

  it('legs out of order are sorted by time', () => {
    // Provide legs in reverse order — should still compute correctly
    const legs: CampaignLeg[] = [
      makeLeg({ legId: '2', legType: 'close', side: 'sell', quantity: 5, avgPrice: 150, startedAt: '2026-01-01T14:00:00Z' }),
      makeLeg({ legType: 'open', side: 'buy', quantity: 5, avgPrice: 100, startedAt: '2026-01-01T10:00:00Z' }),
    ];
    const timestamps = [
      '2026-01-01T10:00:00Z',
      '2026-01-01T14:00:00Z',
    ];
    const prices = [100, 150];

    const pnl = computeCampaignRunningPnl(legs, 'long', timestamps, prices);

    // T10: open 5@100, close=100 → 0
    expect(pnl[0]).toBe(0);
    // T14: closed at 150 → realized = (150-100)*5 = 250
    expect(pnl[1]).toBe(250);
  });
});
