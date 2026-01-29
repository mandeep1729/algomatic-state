export interface Ticker {
  symbol: string;
  name: string | null;
  exchange: string | null;
  is_active: boolean;
  timeframes: string[];
}

export interface OHLCVData {
  timestamps: string[];
  open: number[];
  high: number[];
  low: number[];
  close: number[];
  volume: number[];
}

export interface FeatureData {
  timestamps: string[];
  features: Record<string, number[]>;
  feature_names: string[];
}

export interface OHLCVStats {
  total_bars: number;
  date_range: {
    start: string;
    end: string;
  };
  price: {
    min: number;
    max: number;
    mean: number;
    std: number;
    current: number;
  };
  volume: {
    min: number;
    max: number;
    mean: number;
    total: number;
  };
  returns: {
    total_return: number;
    daily_volatility: number;
  };
}

export interface FeatureStats {
  [key: string]: {
    min: number;
    max: number;
    mean: number;
    std: number;
    median: number;
  };
}

export interface Statistics {
  ohlcv_stats: OHLCVStats;
  feature_stats: FeatureStats;
}

export interface ChartSettings {
  showVolume: boolean;
  showStates: boolean;
  selectedFeatures: string[];
}

export interface StateInfo {
  state_id: number;
  label: string;
  short_label: string;
  color: string;
  description: string;
}

export interface RegimeData {
  timestamps: string[];
  state_ids: number[];
  state_info: Record<string, StateInfo>;
}
