import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IndicatorLabPage } from "./IndicatorLabPage";

const CALCULATE_RESPONSE = {
  symbol: "EURUSD",
  timeframe: "M1",
  timestamps: ["2026-01-01T10:00:00Z", "2026-01-01T10:01:00Z"],
  close: [1.1, 1.2],
  indicators: {
    SMA_20: { parameters: { period: 20 }, series: { value: [null, 1.15] } },
    RSI_14: { parameters: { period: 14 }, series: { value: [null, 55.0] } },
  },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("IndicatorLabPage", () => {
  it("renders the form", () => {
    render(<IndicatorLabPage />);
    expect(screen.getByRole("heading", { name: /Indicator Lab/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("EURUSD")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Calcular/i })).toBeInTheDocument();
  });

  it("calculates and renders results on submit", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({ ok: true, json: () => Promise.resolve(CALCULATE_RESPONSE) }),
      ) as unknown as typeof fetch,
    );

    render(<IndicatorLabPage />);

    fireEvent.change(screen.getByPlaceholderText("EURUSD"), { target: { value: "EURUSD" } });
    const [startInput, endInput] = screen.getAllByDisplayValue("");
    fireEvent.change(startInput, { target: { value: "2026-01-01T10:00" } });
    fireEvent.change(endInput, { target: { value: "2026-01-01T10:05" } });

    fireEvent.click(screen.getByRole("button", { name: /Calcular/i }));

    await waitFor(() => expect(screen.getByText("Últimos valores")).toBeInTheDocument());
    expect(screen.getByText("SMA_20")).toBeInTheDocument();
  });
});
