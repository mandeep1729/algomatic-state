import type { BehavioralTag } from '../../types';

export const MOCK_BEHAVIORAL_TAGS: BehavioralTag[] = [
  // Emotional
  { name: 'revenge_trade', category: 'emotional', description: 'Traded to recover a previous loss' },
  { name: 'fomo', category: 'emotional', description: 'Fear of missing out drove the entry' },
  { name: 'overconfidence', category: 'emotional', description: 'Excessive certainty led to oversizing or skipping checks' },
  { name: 'fear_exit', category: 'emotional', description: 'Exited early due to fear, not plan' },

  // Process
  { name: 'rushed_entry', category: 'process', description: 'Entered without completing pre-trade checklist' },
  { name: 'followed_plan', category: 'process', description: 'Followed the trading plan exactly' },
  { name: 'lesson_learned', category: 'process', description: 'Mistake identified and noted for improvement' },
  { name: 'self_awareness', category: 'process', description: 'Recognized emotional state before/during trade' },
  { name: 'discipline', category: 'process', description: 'Maintained discipline despite urge to deviate' },
  { name: 'patience', category: 'process', description: 'Waited for proper setup before entering' },

  // Risk
  { name: 'no_stop_loss', category: 'risk', description: 'Trade placed without a stop loss' },
  { name: 'oversized', category: 'risk', description: 'Position size exceeded risk guidelines' },
  { name: 'strategy_mismatch', category: 'risk', description: 'Trade did not match any declared strategy' },

  // Timing
  { name: 'poor_timing', category: 'timing', description: 'Entry timing was suboptimal' },
  { name: 'extreme_volatility', category: 'timing', description: 'Traded during extreme volatility conditions' },
  { name: 'open_window', category: 'timing', description: 'Traded in first 15 minutes of market open' },
];
