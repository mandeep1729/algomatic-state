import axios from 'axios';
import type { Ticker, OHLCVData, FeatureData, Statistics, RegimeData } from './types';

const API_BASE = '/api';

export async function fetchTickers(): Promise<Ticker[]> {
  const response = await axios.get<Ticker[]>(`${API_BASE}/tickers`);
  return response.data;
}

export async function fetchOHLCVData(
  symbol: string,
  timeframe: string = '1Min',
  startDate?: string,
  endDate?: string
): Promise<OHLCVData> {
  const params = new URLSearchParams();
  params.append('timeframe', timeframe);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  const response = await axios.get<OHLCVData>(
    `${API_BASE}/ohlcv/${symbol}?${params.toString()}`
  );
  return response.data;
}

export async function fetchFeatures(
  symbol: string,
  timeframe: string = '1Min',
  startDate?: string,
  endDate?: string
): Promise<FeatureData> {
  const params = new URLSearchParams();
  params.append('timeframe', timeframe);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  const response = await axios.get<FeatureData>(
    `${API_BASE}/features/${symbol}?${params.toString()}`
  );
  return response.data;
}

export async function fetchStatistics(
  symbol: string,
  timeframe: string = '1Min',
  startDate?: string,
  endDate?: string
): Promise<Statistics> {
  const params = new URLSearchParams();
  params.append('timeframe', timeframe);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  const response = await axios.get<Statistics>(
    `${API_BASE}/statistics/${symbol}?${params.toString()}`
  );
  return response.data;
}

export async function clearCache(): Promise<void> {
  await axios.delete(`${API_BASE}/cache`);
}

export interface TickerSummary {
  symbol: string;
  timeframes: {
    [key: string]: {
      earliest: string | null;
      latest: string | null;
      bar_count: number;
    };
  };
}

export async function fetchTickerSummary(symbol: string): Promise<TickerSummary> {
  const response = await axios.get<TickerSummary>(`${API_BASE}/tickers/${symbol}/summary`);
  return response.data;
}

export interface ComputeFeaturesResponse {
  symbol: string;
  timeframes_processed: number;
  timeframes_skipped: number;
  features_stored: number;
  message: string;
}

export async function computeFeatures(symbol: string): Promise<ComputeFeaturesResponse> {
  const response = await axios.post<ComputeFeaturesResponse>(
    `${API_BASE}/compute-features/${symbol}`
  );
  return response.data;
}

export async function fetchRegimes(
  symbol: string,
  timeframe: string = '1Min',
  modelId?: string,
  startDate?: string,
  endDate?: string
): Promise<RegimeData> {
  const params = new URLSearchParams();
  params.append('timeframe', timeframe);
  if (modelId) params.append('model_id', modelId);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  const response = await axios.get<RegimeData>(
    `${API_BASE}/regimes/${symbol}?${params.toString()}`
  );
  return response.data;
}

export async function fetchPCARegimes(
  symbol: string,
  timeframe: string = '1Min',
  modelId?: string,
  startDate?: string,
  endDate?: string
): Promise<RegimeData> {
  const params = new URLSearchParams();
  params.append('timeframe', timeframe);
  if (modelId) params.append('model_id', modelId);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  const response = await axios.get<RegimeData>(
    `${API_BASE}/pca/regimes/${symbol}?${params.toString()}`
  );
  return response.data;
}

export interface AnalyzeResponse {
  symbol: string;
  timeframe: string;
  features_computed: number;
  model_trained: boolean;
  model_id: string | null;
  states_computed: number;
  total_bars: number;
  message: string;
}

export interface PCAAnalyzeResponse {
  symbol: string;
  timeframe: string;
  features_computed: number;
  model_trained: boolean;
  model_id: string | null;
  states_computed: number;
  n_components: number;
  n_states: number;
  total_variance_explained: number;
  message: string;
}

export async function analyzeSymbol(
  symbol: string,
  timeframe: string = '1Min'
): Promise<AnalyzeResponse> {
  const params = new URLSearchParams();
  params.append('timeframe', timeframe);

  const response = await axios.post<AnalyzeResponse>(
    `${API_BASE}/analyze/${symbol}?${params.toString()}`
  );
  return response.data;
}

export async function analyzePCASymbol(
  symbol: string,
  timeframe: string = '1Min'
): Promise<PCAAnalyzeResponse> {
  const params = new URLSearchParams();
  params.append('timeframe', timeframe);

  const response = await axios.post<PCAAnalyzeResponse>(
    `${API_BASE}/pca/analyze/${symbol}?${params.toString()}`
  );
  return response.data;
}
