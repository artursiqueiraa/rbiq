import type { DataQuality, ImportJob } from "../types/data";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  return (await response.json()) as T;
}

export const dataService = {
  getImports: (limit = 50) => getJson<ImportJob[]>(`/api/data/imports?limit=${limit}`),
  getQuality: (symbol: string, timeframe: string) =>
    getJson<DataQuality>(
      `/api/candles/quality?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`,
    ),
};
