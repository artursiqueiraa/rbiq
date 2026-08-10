import type { DatabaseHealthResponse, HealthResponse } from "../types/system";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  return (await response.json()) as T;
}

export const systemService = {
  getHealth: () => getJson<HealthResponse>("/api/system/health"),
  getDatabaseHealth: () => getJson<DatabaseHealthResponse>("/api/system/health/database"),
};
