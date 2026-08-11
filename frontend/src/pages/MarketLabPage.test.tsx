import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MarketLabPage } from "./MarketLabPage";

const SNAPSHOT_RESPONSE = {
  symbol: "EURUSD",
  timeframe: "M1",
  timestamp: "2026-01-01T00:21:00Z",
  direction: "BULLISH",
  structure_state: "BULLISH",
  regime: "TRENDING_BULLISH",
  volatility: "NORMAL",
  volatility_value: 0.001,
  trend_strength: 0.5,
  latest_swing_high: {
    type: "HIGH",
    timestamp: "2026-01-01T00:13:00Z",
    confirmation_timestamp: "2026-01-01T00:15:00Z",
    price: 22.5,
    index: 13,
    strength: 3,
  },
  latest_swing_low: {
    type: "LOW",
    timestamp: "2026-01-01T00:16:00Z",
    confirmation_timestamp: "2026-01-01T00:18:00Z",
    price: 16.5,
    index: 16,
    strength: 2.5,
  },
  supports: [],
  resistances: [],
  structure_events: [],
};

const STRUCTURE_RESPONSE = {
  symbol: "EURUSD",
  timeframe: "M1",
  state: "BULLISH",
  swing_highs: [SNAPSHOT_RESPONSE.latest_swing_high],
  swing_lows: [SNAPSHOT_RESPONSE.latest_swing_low],
  events: [],
};

const CANDLES_RESPONSE = [{ timestamp: "2026-01-01T00:00:00Z", open: 10, high: 10.5, low: 9.5, close: 10 }];

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("MarketLabPage", () => {
  it("renders the form", () => {
    render(<MarketLabPage />);
    expect(screen.getByRole("heading", { name: /Market Lab/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("EURUSD")).toBeInTheDocument();
  });

  it("calculates and renders the market snapshot on submit", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        let body: unknown = {};
        if (url.includes("/api/market/snapshot")) body = SNAPSHOT_RESPONSE;
        else if (url.includes("/api/market/structure")) body = STRUCTURE_RESPONSE;
        else if (url.includes("/api/candles")) body = CANDLES_RESPONSE;
        return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
      }) as unknown as typeof fetch,
    );

    render(<MarketLabPage />);

    fireEvent.change(screen.getByPlaceholderText("EURUSD"), { target: { value: "EURUSD" } });
    fireEvent.change(screen.getByLabelText("Timestamp"), { target: { value: "2026-01-01T00:21" } });
    fireEvent.click(screen.getByRole("button", { name: /Calcular snapshot/i }));

    await waitFor(() => expect(screen.getByText("TRENDING_BULLISH")).toBeInTheDocument());
    expect(screen.getAllByText("BULLISH").length).toBeGreaterThan(0);
  });
});
