export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface DatabaseHealthResponse {
  status: string;
  database: string;
}

export type ConnectionStatus = "checking" | "connected" | "disconnected";
