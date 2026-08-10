import type { ConnectionStatus } from "../types/system";

const LABELS: Record<ConnectionStatus, string> = {
  checking: "verificando...",
  connected: "conectado",
  disconnected: "desconectado",
};

export function StatusRow({ label, status }: { label: string; status: ConnectionStatus }) {
  return (
    <div className="status-row" data-status={status}>
      <span className="status-row__label">{label}</span>
      <span className="status-row__value">{LABELS[status]}</span>
    </div>
  );
}
