export interface Signal {
  id: string;
  strategy: string;
  symbol: string;
  timeframe: string;
  timestamp: string;
  direction: "CALL" | "PUT";
  strength: "WEAK" | "MEDIUM" | "STRONG";
  confidence: number;
  expiry_candles: number;
  conditions: string[];
  metadata: Record<string, unknown>;
}

export interface StrategyEvaluation {
  strategy: string;
  signal: Signal | null;
  triggered_conditions: string[];
  failed_conditions: string[];
  evaluated_at: string;
  diagnostics: string[];
}

export const STRATEGY_NAMES = [
  "trend_following",
  "pullback",
  "breakout",
  "mean_reversion",
  "price_action",
  "divergence",
] as const;
