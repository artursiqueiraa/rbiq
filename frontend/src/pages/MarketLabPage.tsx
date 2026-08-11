import { useState } from "react";
import { MarketChart } from "../components/MarketChart";
import { marketService } from "../services/marketService";
import type { CandleOut, MarketSnapshot, StructureHistory } from "../types/market";

const TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"];
const TIMEFRAME_MINUTES: Record<string, number> = { M1: 1, M5: 5, M15: 15, M30: 30, H1: 60, H4: 240, D1: 1440 };
const LOOKBACK_CANDLES = 150;

function toIso(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

export function MarketLabPage() {
  const [symbol, setSymbol] = useState("");
  const [timeframe, setTimeframe] = useState("M1");
  const [timestamp, setTimestamp] = useState("");
  const [snapshot, setSnapshot] = useState<MarketSnapshot | null>(null);
  const [structure, setStructure] = useState<StructureHistory | null>(null);
  const [candles, setCandles] = useState<CandleOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const timestampIso = toIso(timestamp);
    if (!symbol || !timestampIso) {
      setError("Preencha ativo e timestamp.");
      return;
    }

    const lookbackMs = LOOKBACK_CANDLES * TIMEFRAME_MINUTES[timeframe] * 60_000;
    const startIso = new Date(new Date(timestampIso).getTime() - lookbackMs).toISOString();

    setLoading(true);
    try {
      const [snapshotResult, structureResult, candlesResult] = await Promise.all([
        marketService.getSnapshot(symbol, timeframe, timestampIso),
        marketService.getStructure(symbol, timeframe, startIso, timestampIso),
        marketService.getCandles(symbol, timeframe, startIso, timestampIso),
      ]);
      setSnapshot(snapshotResult);
      setStructure(structureResult);
      setCandles(candlesResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao calcular o snapshot de mercado.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="data-center">
      <h1>Market Lab</h1>
      <p className="home-page__subtitle">Estrutura e regime de mercado — apenas contexto, nunca uma decisão de entrada</p>

      <form onSubmit={handleSubmit} className="indicator-form">
        <div className="indicator-form__row">
          <label>
            Ativo
            <input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="EURUSD" />
          </label>
          <label>
            Timeframe
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
              {TIMEFRAMES.map((tf) => (
                <option key={tf} value={tf}>
                  {tf}
                </option>
              ))}
            </select>
          </label>
          <label>
            Timestamp
            <input type="datetime-local" value={timestamp} onChange={(e) => setTimestamp(e.target.value)} />
          </label>
        </div>
        <button type="submit" disabled={loading}>
          {loading ? "Calculando..." : "Calcular snapshot"}
        </button>
      </form>

      {error && <p className="indicator-form__error">{error}</p>}

      {snapshot && (
        <section>
          <h2>Estado do mercado</h2>
          <div className="status-panel">
            <div className="status-row">
              <span className="status-row__label">Direction</span>
              <span className="status-row__value">{snapshot.direction}</span>
            </div>
            <div className="status-row">
              <span className="status-row__label">Structure</span>
              <span className="status-row__value">{snapshot.structure_state}</span>
            </div>
            <div className="status-row">
              <span className="status-row__label">Regime</span>
              <span className="status-row__value">{snapshot.regime}</span>
            </div>
            <div className="status-row">
              <span className="status-row__label">Volatility</span>
              <span className="status-row__value">
                {snapshot.volatility}
                {snapshot.volatility_value !== null ? ` (${(snapshot.volatility_value * 100).toFixed(3)}%)` : ""}
              </span>
            </div>
            <div className="status-row">
              <span className="status-row__label">Trend strength</span>
              <span className="status-row__value">
                {snapshot.trend_strength !== null ? snapshot.trend_strength.toFixed(2) : "—"}
              </span>
            </div>
          </div>

          <h2>Gráfico</h2>
          <p className="home-page__subtitle">
            Círculo vazado = quando o swing aconteceu · círculo cheio = quando foi confirmado · faixas verdes/vermelhas =
            suporte/resistência
          </p>
          <MarketChart
            candles={candles}
            swingHighs={structure?.swing_highs ?? []}
            swingLows={structure?.swing_lows ?? []}
            supports={snapshot.supports}
            resistances={snapshot.resistances}
          />

          <h2>Suportes e resistências</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>Tipo</th>
                <th>Preço</th>
                <th>Faixa</th>
                <th>Toques</th>
                <th>Força</th>
              </tr>
            </thead>
            <tbody>
              {[...snapshot.supports, ...snapshot.resistances].map((zone, i) => (
                <tr key={i}>
                  <td>{zone.kind}</td>
                  <td>{zone.price.toFixed(4)}</td>
                  <td>
                    {zone.lower_bound.toFixed(4)} – {zone.upper_bound.toFixed(4)}
                  </td>
                  <td>{zone.touches}</td>
                  <td>{zone.strength.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}
