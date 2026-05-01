import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { IngestionStatus } from "@/lib/types";

export function useIngestionStatus(taskId?: string) {
  return useQuery({
    queryKey: ["ingestion-status", taskId],
    queryFn: async () => {
      // Endpoint matches backend: /api/v1/ingest/task/{task_id}
      // Assuming api client has /api/v1 base
      const response = await api.get<IngestionStatus>(`/ingest/task/${taskId}`);
      return response.data;
    },
    enabled: !!taskId,
    refetchInterval: (query) => {
      // Stop polling if task is ready (SUCCESS or FAILURE)
      return query.state.data?.ready ? false : 3000;
    },
  });
}
