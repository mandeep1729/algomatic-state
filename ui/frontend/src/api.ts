import axios from 'axios';
import type { DataSource, OHLCVData, FeatureData, RegimeData, Statistics } from './types';

const API_BASE = '/api';

export async function fetchDataSources(): Promise<DataSource[]> {
  const response = await axios.get<DataSource[]>(`${API_BASE}/sources`);
  return response.data;
}

export async function fetchOHLCVData(
  sourceName: string,
  sourceType: string,
  startDate?: string,
  endDate?: string
): Promise<OHLCVData> {
  const params = new URLSearchParams();
  params.append('source_type', sourceType);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  const response = await axios.get<OHLCVData>(
    `${API_BASE}/ohlcv/${sourceName}?${params.toString()}`
  );
  return response.data;
}

export async function fetchFeatures(
  sourceName: string,
  sourceType: string,
  startDate?: string,
  endDate?: string
): Promise<FeatureData> {
  const params = new URLSearchParams();
  params.append('source_type', sourceType);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  const response = await axios.get<FeatureData>(
    `${API_BASE}/features/${sourceName}?${params.toString()}`
  );
  return response.data;
}

export async function fetchRegimes(
  sourceName: string,
  sourceType: string,
  startDate?: string,
  endDate?: string,
  nClusters: number = 5,
  windowSize: number = 60,
  nComponents: number = 8
): Promise<RegimeData> {
  const params = new URLSearchParams();
  params.append('source_type', sourceType);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  params.append('n_clusters', nClusters.toString());
  params.append('window_size', windowSize.toString());
  params.append('n_components', nComponents.toString());

  const response = await axios.get<RegimeData>(
    `${API_BASE}/regimes/${sourceName}?${params.toString()}`
  );
  return response.data;
}

export async function fetchStatistics(
  sourceName: string,
  sourceType: string,
  startDate?: string,
  endDate?: string
): Promise<Statistics> {
  const params = new URLSearchParams();
  params.append('source_type', sourceType);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  const response = await axios.get<Statistics>(
    `${API_BASE}/statistics/${sourceName}?${params.toString()}`
  );
  return response.data;
}

export async function clearCache(): Promise<void> {
  await axios.delete(`${API_BASE}/cache`);
}
