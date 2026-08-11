import { useEffect, useState } from "react";
import { dataService } from "../services/dataService";
import type { DatasetSummary, ImportJob } from "../types/data";

function datasetKey(symbol: string, timeframe: string): string {
  return `${symbol}::${timeframe}`;
}

export function useDataCenter() {
  const [imports, setImports] = useState<ImportJob[]>([]);
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const jobs = await dataService.getImports();
        if (cancelled) return;
        setImports(jobs);

        const uniquePairs = Array.from(
          new Map(jobs.map((job) => [datasetKey(job.symbol, job.timeframe), job])).values(),
        );

        const summaries = await Promise.all(
          uniquePairs.map(async (job): Promise<DatasetSummary> => {
            try {
              const quality = await dataService.getQuality(job.symbol, job.timeframe);
              return { symbol: job.symbol, timeframe: job.timeframe, quality };
            } catch {
              return { symbol: job.symbol, timeframe: job.timeframe, quality: null };
            }
          }),
        );

        if (!cancelled) setDatasets(summaries);
      } catch {
        if (!cancelled) setError("Não foi possível carregar os dados do Data Center.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return { imports, datasets, loading, error };
}
