export interface IndicatorSpec {
  name: string;
  parameters: Record<string, number>;
}

export interface IndicatorSeries {
  parameters: Record<string, number>;
  series: Record<string, (number | null)[]>;
}

export interface IndicatorCalculateResponse {
  symbol: string;
  timeframe: string;
  timestamps: string[];
  close: number[];
  indicators: Record<string, IndicatorSeries>;
}

export const AVAILABLE_INDICATORS: IndicatorSpec[] = [
  { name: "SMA", parameters: { period: 20 } },
  { name: "EMA", parameters: { period: 20 } },
  { name: "RSI", parameters: { period: 14 } },
  { name: "MACD", parameters: { fast_period: 12, slow_period: 26, signal_period: 9 } },
  { name: "BOLLINGER", parameters: { period: 20, std_multiplier: 2 } },
  { name: "ATR", parameters: { period: 14 } },
  { name: "STOCHASTIC", parameters: { k_period: 14, d_period: 3, smooth: 3 } },
  { name: "CCI", parameters: { period: 20 } },
];
