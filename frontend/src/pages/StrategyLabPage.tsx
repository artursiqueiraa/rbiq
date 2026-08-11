import { useState } from "react";
import { strategyService } from "../services/strategyService";
import { STRATEGY_NAMES, type StrategyEvaluation } from "../types/strategy";

const TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"];

function toIso(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

export function StrategyLabPage() {
  const [symbol, setSymbol] = useState("");
  const [timeframe, setTimeframe] = useState("M1");
  const [timestamp, setTimestamp] = useState("");
  const [results, setResults] = useState<Record<string, StrategyEvaluation> | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
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

    setLoading(true);
    try {
      const response = await strategyService.evaluateAll(symbol, timeframe, timestampIso);
      setResults(response);
      setSelected(STRATEGY_NAMES[0]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao avaliar estratégias.");
    } finally {
      setLoading(false);
    }
  }

  const selectedEvaluation = selected && results ? results[selected] : null;

  return (
    <main className="data-center">
      <h1>Strategy Lab</h1>
      <p className="home-page__subtitle">
        Cada estratégia só descreve um sinal de pesquisa — nenhum número aqui é uma probabilidade de vitória
        validada. Isso só existe depois do Backtest Engine (Sprint 6).
      </p>

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
          {loading ? "Avaliando..." : "Avaliar estratégias"}
        </button>
      </form>

      {error && <p className="indicator-form__error">{error}</p>}

      {results && (
        <section>
          <h2>Comparação</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>Estratégia</th>
                <th>Direção</th>
                <th>Força</th>
                <th>Confiança</th>
                <th>Expiry (candles)</th>
              </tr>
            </thead>
            <tbody>
              {STRATEGY_NAMES.map((name) => {
                const evaluation = results[name];
                const signal = evaluation?.signal;
                return (
                  <tr
                    key={name}
                    onClick={() => setSelected(name)}
                    style={{ cursor: "pointer", fontWeight: selected === name ? 600 : 400 }}
                    data-status={signal?.direction ?? "NONE"}
                  >
                    <td>{name}</td>
                    <td>{signal ? signal.direction : "NONE"}</td>
                    <td>{signal ? signal.strength : "—"}</td>
                    <td>{signal ? signal.confidence.toFixed(2) : "—"}</td>
                    <td>{signal ? signal.expiry_candles : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {selectedEvaluation && (
            <>
              <h2>{selected}</h2>
              <div className="status-panel">
                <div className="status-row">
                  <span className="status-row__label">Sinal</span>
                  <span className="status-row__value">
                    {selectedEvaluation.signal ? selectedEvaluation.signal.direction : "NONE"}
                  </span>
                </div>
                {selectedEvaluation.signal && (
                  <>
                    <div className="status-row">
                      <span className="status-row__label">Confidence</span>
                      <span className="status-row__value">{selectedEvaluation.signal.confidence.toFixed(2)}</span>
                    </div>
                    <div className="status-row">
                      <span className="status-row__label">Strength</span>
                      <span className="status-row__value">{selectedEvaluation.signal.strength}</span>
                    </div>
                    <div className="status-row">
                      <span className="status-row__label">Expiry</span>
                      <span className="status-row__value">{selectedEvaluation.signal.expiry_candles} candle(s)</span>
                    </div>
                  </>
                )}
              </div>

              <h3>Condições satisfeitas</h3>
              {selectedEvaluation.triggered_conditions.length === 0 ? (
                <p>Nenhuma.</p>
              ) : (
                <ul>
                  {selectedEvaluation.triggered_conditions.map((c) => (
                    <li key={c}>✓ {c}</li>
                  ))}
                </ul>
              )}

              <h3>Condições não satisfeitas</h3>
              {selectedEvaluation.failed_conditions.length === 0 ? (
                <p>Nenhuma.</p>
              ) : (
                <ul>
                  {selectedEvaluation.failed_conditions.map((c) => (
                    <li key={c}>✗ {c}</li>
                  ))}
                </ul>
              )}

              {selectedEvaluation.diagnostics.length > 0 && (
                <>
                  <h3>Diagnóstico</h3>
                  <ul>
                    {selectedEvaluation.diagnostics.map((d) => (
                      <li key={d}>{d}</li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </section>
      )}
    </main>
  );
}
