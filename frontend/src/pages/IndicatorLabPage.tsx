import { useState } from "react";
import { LineChart } from "../components/LineChart";
import { indicatorService } from "../services/indicatorService";
import { AVAILABLE_INDICATORS, type IndicatorCalculateResponse } from "../types/indicators";

const TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"];
const CHART_COLORS = ["#1a7f37", "#0969da", "#9a6700", "#cf222e", "#8250df"];

function toIsoOrNull(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

export function IndicatorLabPage() {
  const [symbol, setSymbol] = useState("");
  const [timeframe, setTimeframe] = useState("M1");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set(["SMA", "EMA", "RSI"]));
  const [result, setResult] = useState<IndicatorCalculateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function toggle(name: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    const startIso = toIsoOrNull(start);
    const endIso = toIsoOrNull(end);
    if (!symbol || !startIso || !endIso) {
      setError("Preencha ativo, início e fim.");
      return;
    }

    const indicators = AVAILABLE_INDICATORS.filter((i) => selected.has(i.name));
    if (indicators.length === 0) {
      setError("Selecione ao menos um indicador.");
      return;
    }

    setLoading(true);
    try {
      const response = await indicatorService.calculate({ symbol, timeframe, start: startIso, end: endIso, indicators });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao calcular indicadores.");
    } finally {
      setLoading(false);
    }
  }

  const priceSeries = result
    ? [
        { name: "close", color: "#666", values: result.close },
        ...Object.entries(result.indicators)
          .filter(([key]) => key.startsWith("SMA_") || key.startsWith("EMA_"))
          .map(([key, series], i) => ({ name: key, color: CHART_COLORS[i % CHART_COLORS.length], values: series.series.value })),
      ]
    : [];

  const rsiEntry = result ? Object.entries(result.indicators).find(([key]) => key.startsWith("RSI_")) : undefined;

  return (
    <main className="data-center">
      <h1>Indicator Lab</h1>
      <p className="home-page__subtitle">Calcula indicadores técnicos sobre candles já armazenados</p>

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
            Início
            <input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label>
            Fim
            <input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
        </div>

        <div className="indicator-form__checkboxes">
          {AVAILABLE_INDICATORS.map((indicator) => (
            <label key={indicator.name}>
              <input
                type="checkbox"
                checked={selected.has(indicator.name)}
                onChange={() => toggle(indicator.name)}
              />
              {indicator.name}
            </label>
          ))}
        </div>

        <button type="submit" disabled={loading}>
          {loading ? "Calculando..." : "Calcular"}
        </button>
      </form>

      {error && <p className="indicator-form__error">{error}</p>}

      {result && (
        <section>
          <h2>Preço {priceSeries.length > 1 ? "+ médias móveis" : ""}</h2>
          <LineChart series={priceSeries} />

          {rsiEntry && (
            <>
              <h2>{rsiEntry[0]}</h2>
              <LineChart series={[{ name: rsiEntry[0], color: "#0969da", values: rsiEntry[1].series.value }]} />
            </>
          )}

          <h2>Últimos valores</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Close</th>
                {Object.keys(result.indicators).map((key) => (
                  <th key={key}>{key}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.timestamps.slice(-10).map((ts, offset) => {
                const i = result.timestamps.length - 10 + offset;
                return (
                  <tr key={ts}>
                    <td>{new Date(ts).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" })}</td>
                    <td>{result.close[i]}</td>
                    {Object.values(result.indicators).map((series, idx) => {
                      const firstKey = Object.keys(series.series)[0];
                      const value = series.series[firstKey][i];
                      return <td key={idx}>{value === null || value === undefined ? "—" : value.toFixed(4)}</td>;
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}
