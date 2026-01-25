// Feature configuration - mirrors config/features.json

export interface FeatureDefinition {
  name: string;
  description: string;
  category: string;
  lookback: number;
  enabled: boolean;
}

export interface FeatureCategory {
  [featureKey: string]: FeatureDefinition;
}

export interface FeaturesConfig {
  version: string;
  description: string;
  feature_categories: string[];
  features: {
    [category: string]: FeatureCategory;
  };
}

export const FEATURE_CATEGORY_LABELS: Record<string, string> = {
  returns: 'Returns & Trend',
  volatility: 'Volatility',
  volume: 'Volume',
  intrabar: 'Intrabar Structure',
  anchor: 'Anchor & Location',
  time: 'Time of Day',
  market_context: 'Market Context',
  momentum: 'Momentum',
  trend: 'Trend',
  support_resistance: 'Support/Resistance',
};

export const FEATURE_CATEGORY_COLORS: Record<string, string> = {
  returns: '#58a6ff',
  volatility: '#f85149',
  volume: '#3fb950',
  intrabar: '#d29922',
  anchor: '#a371f7',
  time: '#db6d28',
  market_context: '#388bfd',
  momentum: '#ff7b72',
  trend: '#7ee787',
  support_resistance: '#cea5fb',
};

export const featuresConfig: FeaturesConfig = {
  version: '1.0',
  description: 'Technical indicators and features configuration',
  feature_categories: [
    'returns',
    'trend',
    'volatility',
    'volume',
    'intrabar',
    'anchor',
    'time',
    'market_context',
    'momentum',
    'support_resistance',
  ],
  features: {
    returns: {
      r1: { name: '1-Bar Return', description: 'Log return over 1 bar', category: 'returns', lookback: 1, enabled: true },
      r5: { name: '5-Bar Return', description: 'Log return over 5 bars', category: 'returns', lookback: 5, enabled: true },
      r15: { name: '15-Bar Return', description: 'Log return over 15 bars', category: 'returns', lookback: 15, enabled: true },
      r60: { name: '60-Bar Return', description: 'Log return over 60 bars', category: 'returns', lookback: 60, enabled: true },
      cumret_60: { name: 'Cumulative Return', description: 'Cumulative log return over 60 bars', category: 'returns', lookback: 60, enabled: true },
      ema_diff: { name: 'EMA Difference', description: '(EMA12 - EMA48) / price', category: 'returns', lookback: 48, enabled: true },
      slope_60: { name: 'Price Slope', description: 'Linear regression slope over 60 bars', category: 'returns', lookback: 60, enabled: true },
      trend_strength: { name: 'Trend Strength', description: '|slope_60| / rv_60', category: 'returns', lookback: 60, enabled: true },
    },
    volatility: {
      rv_15: { name: 'RV 15', description: '15-bar realized volatility', category: 'volatility', lookback: 15, enabled: true },
      rv_60: { name: 'RV 60', description: '60-bar realized volatility', category: 'volatility', lookback: 60, enabled: true },
      range_1: { name: 'Normalized Range', description: '(H - L) / C', category: 'volatility', lookback: 1, enabled: true },
      atr_60: { name: 'ATR 60', description: 'Average range over 60 bars', category: 'volatility', lookback: 60, enabled: true },
      range_z_60: { name: 'Range Z-Score', description: 'Z-score of range', category: 'volatility', lookback: 60, enabled: true },
      vol_of_vol: { name: 'Vol of Vol', description: 'std(rv_15) over 60 bars', category: 'volatility', lookback: 60, enabled: true },
      atr_14: { name: 'ATR 14', description: 'Average True Range 14', category: 'volatility', lookback: 14, enabled: true },
      bb_upper: { name: 'BB Upper', description: 'Bollinger upper band', category: 'volatility', lookback: 20, enabled: true },
      bb_middle: { name: 'BB Middle', description: 'Bollinger middle band', category: 'volatility', lookback: 20, enabled: true },
      bb_lower: { name: 'BB Lower', description: 'Bollinger lower band', category: 'volatility', lookback: 20, enabled: true },
      bb_width: { name: 'BB Width', description: 'Bollinger band width', category: 'volatility', lookback: 20, enabled: true },
      bb_pct: { name: 'BB %B', description: 'Bollinger %B', category: 'volatility', lookback: 20, enabled: true },
    },
    volume: {
      vol1: { name: 'Volume', description: 'Raw volume', category: 'volume', lookback: 1, enabled: true },
      dvol1: { name: 'Dollar Volume', description: 'close * volume', category: 'volume', lookback: 1, enabled: true },
      relvol_60: { name: 'Relative Volume', description: 'V / mean(V, 60)', category: 'volume', lookback: 60, enabled: true },
      vol_z_60: { name: 'Volume Z-Score', description: 'Volume z-score', category: 'volume', lookback: 60, enabled: true },
      dvol_z_60: { name: 'Dollar Vol Z', description: 'Dollar volume z-score', category: 'volume', lookback: 60, enabled: true },
      obv: { name: 'OBV', description: 'On-Balance Volume', category: 'volume', lookback: 1, enabled: true },
      vwap: { name: 'VWAP', description: 'Volume Weighted Avg Price', category: 'volume', lookback: 60, enabled: true },
    },
    intrabar: {
      clv: { name: 'CLV', description: 'Close location value', category: 'intrabar', lookback: 1, enabled: true },
      body_ratio: { name: 'Body Ratio', description: '|C - O| / (H - L)', category: 'intrabar', lookback: 1, enabled: true },
      upper_wick: { name: 'Upper Wick', description: 'Upper wick ratio', category: 'intrabar', lookback: 1, enabled: true },
      lower_wick: { name: 'Lower Wick', description: 'Lower wick ratio', category: 'intrabar', lookback: 1, enabled: true },
    },
    anchor: {
      vwap_60: { name: 'VWAP 60', description: '60-bar VWAP', category: 'anchor', lookback: 60, enabled: true },
      dist_vwap_60: { name: 'Dist VWAP', description: 'Distance from VWAP', category: 'anchor', lookback: 60, enabled: true },
      dist_ema_48: { name: 'Dist EMA48', description: 'Distance from EMA48', category: 'anchor', lookback: 48, enabled: true },
      breakout_20: { name: 'Breakout 20', description: 'Breakout from 20-bar high', category: 'anchor', lookback: 20, enabled: true },
      pullback_depth: { name: 'Pullback', description: 'Pullback from high', category: 'anchor', lookback: 20, enabled: true },
    },
    time: {
      tod_sin: { name: 'ToD Sine', description: 'Time-of-day sine', category: 'time', lookback: 1, enabled: true },
      tod_cos: { name: 'ToD Cosine', description: 'Time-of-day cosine', category: 'time', lookback: 1, enabled: true },
      is_open_window: { name: 'Open Window', description: 'First 30 min flag', category: 'time', lookback: 1, enabled: true },
      is_close_window: { name: 'Close Window', description: 'Last 60 min flag', category: 'time', lookback: 1, enabled: true },
      is_midday: { name: 'Midday', description: 'Midday flag', category: 'time', lookback: 1, enabled: true },
    },
    market_context: {
      mkt_r5: { name: 'Mkt R5', description: '5-bar market return', category: 'market_context', lookback: 5, enabled: true },
      mkt_r15: { name: 'Mkt R15', description: '15-bar market return', category: 'market_context', lookback: 15, enabled: true },
      mkt_rv_60: { name: 'Mkt Vol', description: 'Market volatility', category: 'market_context', lookback: 60, enabled: true },
      beta_60: { name: 'Beta', description: 'Rolling beta', category: 'market_context', lookback: 60, enabled: true },
      resid_rv_60: { name: 'Resid Vol', description: 'Residual volatility', category: 'market_context', lookback: 60, enabled: true },
    },
    momentum: {
      rsi_14: { name: 'RSI', description: 'RSI 14', category: 'momentum', lookback: 14, enabled: true },
      macd: { name: 'MACD', description: 'MACD Line', category: 'momentum', lookback: 26, enabled: true },
      macd_signal: { name: 'MACD Signal', description: 'MACD Signal', category: 'momentum', lookback: 35, enabled: true },
      macd_hist: { name: 'MACD Hist', description: 'MACD Histogram', category: 'momentum', lookback: 35, enabled: true },
      stoch_k: { name: 'Stoch %K', description: 'Stochastic %K', category: 'momentum', lookback: 14, enabled: true },
      stoch_d: { name: 'Stoch %D', description: 'Stochastic %D', category: 'momentum', lookback: 14, enabled: true },
      adx_14: { name: 'ADX', description: 'ADX 14', category: 'momentum', lookback: 14, enabled: true },
      cci_20: { name: 'CCI', description: 'CCI 20', category: 'momentum', lookback: 20, enabled: true },
      willr_14: { name: 'Williams %R', description: 'Williams %R', category: 'momentum', lookback: 14, enabled: true },
      mfi_14: { name: 'MFI', description: 'Money Flow Index', category: 'momentum', lookback: 14, enabled: true },
    },
    trend: {
      sma_20: { name: 'SMA 20', description: 'SMA 20', category: 'trend', lookback: 20, enabled: true },
      sma_50: { name: 'SMA 50', description: 'SMA 50', category: 'trend', lookback: 50, enabled: true },
      sma_200: { name: 'SMA 200', description: 'SMA 200', category: 'trend', lookback: 200, enabled: true },
      ema_20: { name: 'EMA 20', description: 'EMA 20', category: 'trend', lookback: 20, enabled: true },
      ema_50: { name: 'EMA 50', description: 'EMA 50', category: 'trend', lookback: 50, enabled: true },
      ema_200: { name: 'EMA 200', description: 'EMA 200', category: 'trend', lookback: 200, enabled: true },
      psar: { name: 'PSAR', description: 'Parabolic SAR', category: 'trend', lookback: 1, enabled: true },
      ichi_tenkan: { name: 'Tenkan', description: 'Ichimoku Tenkan', category: 'trend', lookback: 9, enabled: true },
      ichi_kijun: { name: 'Kijun', description: 'Ichimoku Kijun', category: 'trend', lookback: 26, enabled: true },
      ichi_senkou_a: { name: 'Senkou A', description: 'Ichimoku Senkou A', category: 'trend', lookback: 26, enabled: true },
      ichi_senkou_b: { name: 'Senkou B', description: 'Ichimoku Senkou B', category: 'trend', lookback: 52, enabled: true },
      ichi_chikou: { name: 'Chikou', description: 'Ichimoku Chikou', category: 'trend', lookback: 26, enabled: true },
    },
    support_resistance: {
      pivot_pp: { name: 'Pivot', description: 'Pivot Point', category: 'support_resistance', lookback: 1, enabled: true },
      pivot_r1: { name: 'R1', description: 'Resistance 1', category: 'support_resistance', lookback: 1, enabled: true },
      pivot_r2: { name: 'R2', description: 'Resistance 2', category: 'support_resistance', lookback: 1, enabled: true },
      pivot_s1: { name: 'S1', description: 'Support 1', category: 'support_resistance', lookback: 1, enabled: true },
      pivot_s2: { name: 'S2', description: 'Support 2', category: 'support_resistance', lookback: 1, enabled: true },
    },
  },
};

// Get all feature keys as a flat list
export function getAllFeatureKeys(): string[] {
  const keys: string[] = [];
  for (const category of Object.values(featuresConfig.features)) {
    keys.push(...Object.keys(category));
  }
  return keys;
}

// Get feature definition by key
export function getFeatureDefinition(key: string): FeatureDefinition | null {
  for (const category of Object.values(featuresConfig.features)) {
    if (key in category) {
      return category[key];
    }
  }
  return null;
}

// Get category for a feature key
export function getFeatureCategory(key: string): string | null {
  for (const [categoryName, category] of Object.entries(featuresConfig.features)) {
    if (key in category) {
      return categoryName;
    }
  }
  return null;
}
