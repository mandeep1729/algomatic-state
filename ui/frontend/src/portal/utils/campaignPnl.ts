import type { CampaignLeg } from '../types';

/**
 * Compute running (unrealized + realized) PNL for a campaign at each OHLCV timestamp.
 * Tracks net position from legs and marks-to-market against close prices.
 *
 * Uses legType (not side) to determine whether a leg opens or closes position,
 * so it works correctly for both long and short campaigns.
 */
export function computeCampaignRunningPnl(
  legs: CampaignLeg[],
  direction: 'long' | 'short',
  ohlcvTimestamps: string[],
  closePrices: number[],
): number[] {
  const dirSign = direction === 'long' ? 1 : -1;

  // Build position events from legs sorted by time.
  // Use legType (not side) to determine direction: open/add increase position,
  // reduce/close decrease it. This works for both long and short campaigns.
  const events = legs
    .map((leg) => {
      const isOpening = leg.legType === 'open' || leg.legType === 'add';
      return {
        timeMs: new Date(leg.startedAt).getTime(),
        deltaQty: isOpening ? leg.quantity : -leg.quantity,
        price: leg.avgPrice,
      };
    })
    .sort((a, b) => a.timeMs - b.timeMs);

  const pnl: number[] = [];
  let netQty = 0;
  let totalCost = 0; // running cost basis (signed by direction)
  let realizedPnl = 0;
  let eventIdx = 0;

  for (let i = 0; i < ohlcvTimestamps.length; i++) {
    const tsMs = new Date(ohlcvTimestamps[i]).getTime();

    // Process any legs that occurred at or before this timestamp
    while (eventIdx < events.length && events[eventIdx].timeMs <= tsMs) {
      const ev = events[eventIdx];
      if (ev.deltaQty > 0) {
        // Adding to position
        totalCost += ev.price * ev.deltaQty;
        netQty += ev.deltaQty;
      } else {
        // Reducing position — realize PnL on closed portion
        const closingQty = Math.abs(ev.deltaQty);
        const avgCost = netQty > 0 ? totalCost / netQty : ev.price;
        realizedPnl += (ev.price - avgCost) * closingQty * dirSign;
        totalCost -= avgCost * closingQty;
        netQty -= closingQty;
      }
      eventIdx++;
    }

    // Mark-to-market unrealized PnL on remaining position
    const avgCost = netQty > 0 ? totalCost / netQty : 0;
    const unrealizedPnl = netQty > 0
      ? (closePrices[i] - avgCost) * netQty * dirSign
      : 0;

    pnl.push(+(realizedPnl + unrealizedPnl).toFixed(2));
  }

  return pnl;
}
