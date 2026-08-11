import type { CandleOut, MarketSnapshot, StructureHistory } from "../types/market";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export const marketService = {
  getSnapshot: (symbol: string, timeframe: string, timestamp: string) =>
    getJson<MarketSnapshot>(
      `/api/market/snapshot?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&timestamp=${encodeURIComponent(timestamp)}`,
    ),

  getStructure: (symbol: string, timeframe: string, start: string, end: string) =>
    getJson<StructureHistory>(
      `/api/market/structure?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`,
    ),

  getCandles: (symbol: string, timeframe: string, start: string, end: string) =>
    getJson<CandleOut[]>(
      `/api/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`,
    ),
};
