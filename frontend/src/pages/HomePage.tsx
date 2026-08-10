import { StatusRow } from "../components/StatusRow";
import { useSystemStatus } from "../hooks/useSystemStatus";

export function HomePage() {
  const { apiStatus, databaseStatus, version } = useSystemStatus();

  return (
    <main className="home-page">
      <h1>IQO Strategy Lab</h1>
      <p className="home-page__subtitle">Laboratório de pesquisa e análise quantitativa</p>

      <div className="status-panel">
        <StatusRow label="API" status={apiStatus} />
        <StatusRow label="Database" status={databaseStatus} />
        <div className="status-row">
          <span className="status-row__label">Environment</span>
          <span className="status-row__value">development</span>
        </div>
        {version && (
          <div className="status-row">
            <span className="status-row__label">Version</span>
            <span className="status-row__value">{version}</span>
          </div>
        )}
      </div>
    </main>
  );
}
