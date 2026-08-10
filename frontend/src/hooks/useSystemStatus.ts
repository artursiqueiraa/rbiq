import { useEffect, useState } from "react";
import { systemService } from "../services/systemService";
import type { ConnectionStatus } from "../types/system";

export function useSystemStatus() {
  const [apiStatus, setApiStatus] = useState<ConnectionStatus>("checking");
  const [databaseStatus, setDatabaseStatus] = useState<ConnectionStatus>("checking");
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    systemService
      .getHealth()
      .then((health) => {
        setApiStatus("connected");
        setVersion(health.version);
      })
      .catch(() => setApiStatus("disconnected"));

    systemService
      .getDatabaseHealth()
      .then((health) => setDatabaseStatus(health.status === "healthy" ? "connected" : "disconnected"))
      .catch(() => setDatabaseStatus("disconnected"));
  }, []);

  return { apiStatus, databaseStatus, version };
}
