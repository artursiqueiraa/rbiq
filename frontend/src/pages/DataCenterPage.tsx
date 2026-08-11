import { useDataCenter } from "../hooks/useDataCenter";

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" });
}

export function DataCenterPage() {
  const { imports, datasets, loading, error } = useDataCenter();

  if (loading) return <main className="data-center">Carregando...</main>;
  if (error) return <main className="data-center">{error}</main>;

  return (
    <main className="data-center">
      <h1>Data Center</h1>
      <p className="home-page__subtitle">Datasets importados e sua qualidade — timestamps exibidos em America/Sao_Paulo</p>

      <section>
        <h2>Datasets</h2>
        {datasets.length === 0 ? (
          <p>Nenhum dataset importado ainda.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Ativo</th>
                <th>Timeframe</th>
                <th>Candles</th>
                <th>Último candle</th>
                <th>Gaps</th>
                <th>Qualidade</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((dataset) => (
                <tr key={`${dataset.symbol}-${dataset.timeframe}`}>
                  <td>{dataset.symbol}</td>
                  <td>{dataset.timeframe}</td>
                  <td>{dataset.quality?.total_candles ?? "—"}</td>
                  <td>{formatTimestamp(dataset.quality?.last_timestamp ?? null)}</td>
                  <td>{dataset.quality?.gaps ?? "—"}</td>
                  <td>{dataset.quality ? `${dataset.quality.quality_score.toFixed(1)}` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h2>Histórico de importações</h2>
        {imports.length === 0 ? (
          <p>Nenhuma importação registrada ainda.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Arquivo</th>
                <th>Ativo</th>
                <th>Timeframe</th>
                <th>Status</th>
                <th>Total</th>
                <th>Válidos</th>
                <th>Inválidos</th>
                <th>Iniciado em</th>
              </tr>
            </thead>
            <tbody>
              {imports.map((job) => (
                <tr key={job.id} data-status={job.status}>
                  <td>{job.source_file}</td>
                  <td>{job.symbol}</td>
                  <td>{job.timeframe}</td>
                  <td>{job.status}</td>
                  <td>{job.total_rows}</td>
                  <td>{job.valid_rows}</td>
                  <td>{job.invalid_rows}</td>
                  <td>{formatTimestamp(job.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
