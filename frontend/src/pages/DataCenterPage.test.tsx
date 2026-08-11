import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DataCenterPage } from "./DataCenterPage";

const IMPORTS_RESPONSE = [
  {
    id: 1,
    provider: "csv",
    source_file: "data/raw/test/eurusd_m1_sample.csv",
    symbol: "EURUSD",
    timeframe: "M1",
    started_at: "2026-01-01T10:00:00Z",
    finished_at: "2026-01-01T10:00:01Z",
    status: "PARTIAL",
    total_rows: 10,
    valid_rows: 6,
    invalid_rows: 4,
    duplicates: 1,
    gaps: 1,
  },
];

const QUALITY_RESPONSE = {
  symbol: "EURUSD",
  timeframe: "M1",
  total_candles: 5,
  valid_candles: 5,
  invalid_candles: 0,
  duplicates: 0,
  gaps: 1,
  out_of_order: 0,
  first_gap: "2026-01-01T10:02:00Z",
  last_gap: "2026-01-01T10:02:00Z",
  last_timestamp: "2026-01-01T10:05:00Z",
  quality_score: 99.0,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DataCenterPage", () => {
  it("renders datasets and import history from the API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        const body = url.includes("/api/data/imports") ? IMPORTS_RESPONSE : QUALITY_RESPONSE;
        return Promise.resolve({ json: () => Promise.resolve(body) });
      }) as unknown as typeof fetch,
    );

    render(<DataCenterPage />);

    await waitFor(() => expect(screen.getAllByText("EURUSD").length).toBeGreaterThan(0));
    expect(screen.getByText("data/raw/test/eurusd_m1_sample.csv")).toBeInTheDocument();
    expect(screen.getByText("PARTIAL")).toBeInTheDocument();
  });
});
