import type { StrategyEvaluation } from "../types/strategy";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail ?? `request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export const strategyService = {
  evaluate: (strategy: string, symbol: string, timeframe: string, timestamp: string) =>
    postJson<StrategyEvaluation>("/api/strategies/evaluate", { strategy, symbol, timeframe, timestamp }),

  evaluateAll: (symbol: string, timeframe: string, timestamp: string) =>
    postJson<Record<string, StrategyEvaluation>>("/api/strategies/evaluate-all", { symbol, timeframe, timestamp }),
};
