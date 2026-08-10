import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

vi.stubGlobal(
  "fetch",
  vi.fn(() =>
    Promise.resolve({
      json: () => Promise.resolve({ status: "healthy", service: "iqo-strategy-lab", version: "0.1.0" }),
    }),
  ) as unknown as typeof fetch,
);

describe("App", () => {
  it("renders the main heading", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /IQO Strategy Lab/i })).toBeInTheDocument();
  });
});
