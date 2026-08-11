import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StrategyLabPage } from "./StrategyLabPage";

function makeEvaluation(strategy: string, direction: "CALL" | "PUT" | null) {
  return {
    strategy,
    signal: direction
      ? {
          id: `${strategy}:X`,
          strategy,
          symbol: "EURUSD",
          timeframe: "M1",
          timestamp: "2026-01-01T00:00:00Z",
          direction,
          strength: "STRONG",
          confidence: 1.0,
          expiry_candles: 1,
          conditions: ["regime_compatible"],
          metadata: {},
        }
      : null,
    triggered_conditions: ["regime_compatible"],
    failed_conditions: [],
    evaluated_at: "2026-01-01T00:00:00Z",
    diagnostics: [],
  };
}

const EVALUATE_ALL_RESPONSE = {
  trend_following: makeEvaluation("trend_following", "CALL"),
  pullback: makeEvaluation("pullback", null),
  breakout: makeEvaluation("breakout", null),
  mean_reversion: makeEvaluation("mean_reversion", null),
  price_action: makeEvaluation("price_action", "CALL"),
  divergence: makeEvaluation("divergence", null),
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("StrategyLabPage", () => {
  it("renders the form", () => {
    render(<StrategyLabPage />);
    expect(screen.getByRole("heading", { name: /Strategy Lab/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("EURUSD")).toBeInTheDocument();
  });

  it("evaluates and renders the comparison table on submit", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({ ok: true, json: () => Promise.resolve(EVALUATE_ALL_RESPONSE) }),
      ) as unknown as typeof fetch,
    );

    render(<StrategyLabPage />);

    fireEvent.change(screen.getByPlaceholderText("EURUSD"), { target: { value: "EURUSD" } });
    fireEvent.change(screen.getByLabelText("Timestamp"), { target: { value: "2026-01-01T00:00" } });
    fireEvent.click(screen.getByRole("button", { name: /Avaliar estratégias/i }));

    await waitFor(() => expect(screen.getByText("Comparação")).toBeInTheDocument());
    expect(screen.getAllByText("trend_following").length).toBeGreaterThan(0);
    expect(screen.getAllByText("CALL").length).toBeGreaterThan(0);
    expect(screen.getAllByText("NONE").length).toBeGreaterThan(0);
  });
});
