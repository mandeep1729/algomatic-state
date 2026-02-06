import type { User, TradingProfile, RiskPreferences } from '../types';

export const MOCK_USER: User = {
  id: 1,
  email: 'trader@example.com',
  name: 'Demo Trader',
  onboarding_complete: true,
  created_at: '2025-01-15T10:00:00Z',
};

export const MOCK_PROFILE: TradingProfile = {
  experience_level: 'intermediate',
  trading_style: 'day_trading',
  primary_markets: ['US_EQUITIES'],
  typical_timeframes: ['1Min', '15Min', '1Hour'],
  account_size_range: '$10k-$50k',
};

export const MOCK_RISK_PREFERENCES: RiskPreferences = {
  max_loss_per_trade_pct: 2.0,
  max_daily_loss_pct: 5.0,
  max_open_positions: 5,
  risk_reward_minimum: 1.5,
  stop_loss_required: true,
};
