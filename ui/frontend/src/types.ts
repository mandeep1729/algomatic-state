export interface DataSource {
  name: string;
  type: 'local' | 'alpaca';
  path: string | null;
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

export interface RegimeInfo {
  label: number;
  size: number;
  mean_return: number;
  std_return: number;
  sharpe: number;
}

export interface RegimeData {
  timestamps: string[];
  regime_labels: number[];
  regime_info: RegimeInfo[];
  transition_matrix: number[][];
  explained_variance: number;
  n_samples: number;
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
  regime_stats: {
    n_regimes?: number;
    regimes?: RegimeInfo[];
    explained_variance?: number;
  };
}

export interface ChartSettings {
  showVolume: boolean;
  showRegimes: boolean;
  selectedFeatures: string[];
}

export interface RegimeParams {
  n_clusters: number;
  window_size: number;
  n_components: number;
}
