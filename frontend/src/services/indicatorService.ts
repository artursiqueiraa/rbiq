import type { IndicatorCalculateResponse, IndicatorSpec } from "../types/indicators";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface CalculateParams {
  symbol: string;
  timeframe: string;
  start: string;
  end: string;
  indicators: IndicatorSpec[];
}

export const indicatorService = {
  async calculate(params: CalculateParams): Promise<IndicatorCalculateResponse> {
    const response = await fetch(`${API_BASE_URL}/api/indicators/calculate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail ?? `request failed with status ${response.status}`);
    }
    return (await response.json()) as IndicatorCalculateResponse;
  },
};
