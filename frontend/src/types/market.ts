export interface SwingPoint {
  type: "HIGH" | "LOW";
  timestamp: string;
  confirmation_timestamp: string;
  price: number;
  index: number;
  strength: number;
}

export interface StructureEvent {
  event_type: string;
  timestamp: string;
  confirmation_timestamp: string;
  price: number;
  metadata: Record<string, string>;
}

export interface Zone {
  kind: "SUPPORT" | "RESISTANCE";
  price: number;
  lower_bound: number;
  upper_bound: number;
  touches: number;
  strength: number;
  first_seen: string;
  last_seen: string;
}

export interface MarketSnapshot {
  symbol: string;
  timeframe: string;
  timestamp: string | null;
  direction: string;
  structure_state: string;
  regime: string;
  volatility: string;
  volatility_value: number | null;
  trend_strength: number | null;
  latest_swing_high: SwingPoint | null;
  latest_swing_low: SwingPoint | null;
  supports: Zone[];
  resistances: Zone[];
  structure_events: StructureEvent[];
}

export interface StructureHistory {
  symbol: string;
  timeframe: string;
  state: string;
  swing_highs: SwingPoint[];
  swing_lows: SwingPoint[];
  events: StructureEvent[];
}

export interface CandleOut {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
}
