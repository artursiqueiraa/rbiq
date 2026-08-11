export interface ImportJob {
  id: number;
  provider: string;
  source_file: string;
  symbol: string;
  timeframe: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  duplicates: number;
  gaps: number;
}

export interface DataQuality {
  symbol: string;
  timeframe: string;
  total_candles: number;
  valid_candles: number;
  invalid_candles: number;
  duplicates: number;
  gaps: number;
  out_of_order: number;
  first_gap: string | null;
  last_gap: string | null;
  last_timestamp: string | null;
  quality_score: number;
}

export interface DatasetSummary {
  symbol: string;
  timeframe: string;
  quality: DataQuality | null;
}
