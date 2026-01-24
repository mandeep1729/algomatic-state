import axios from 'axios';
import type { Ticker, OHLCVData, FeatureData, RegimeData, Statistics } from './types';

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

export async function fetchRegimes(
  symbol: string,
  timeframe: string = '1Min',
  startDate?: string,
  endDate?: string,
  nClusters: number = 5,
  windowSize: number = 60,
  nComponents: number = 8
): Promise<RegimeData> {
  const params = new URLSearchParams();
  params.append('timeframe', timeframe);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  params.append('n_clusters', nClusters.toString());
  params.append('window_size', windowSize.toString());
  params.append('n_components', nComponents.toString());

  const response = await axios.get<RegimeData>(
    `${API_BASE}/regimes/${symbol}?${params.toString()}`
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
