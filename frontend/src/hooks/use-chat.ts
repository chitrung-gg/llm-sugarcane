import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { ChatHistory, Thread } from "@/lib/types";

export function useChatHistory(threadId?: string) {
  return useQuery({
    queryKey: ["chat-history", threadId],
    queryFn: async () => {
      const response = await api.get<ChatHistory>(`/agent/${threadId}/history`);
      return response.data;
    },
    enabled: !!threadId,
  });
}

export function useSendMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { 
      query: string; 
      threadId: string; 
      projectId: string; 
      datasetIds: string[] 
    }) => {
      const formData = new FormData();
      formData.append("query", data.query);
      formData.append("thread_id", data.threadId);
      formData.append("project_id", data.projectId);
      if (data.datasetIds.length > 0) {
        formData.append("dataset_ids", JSON.stringify(data.datasetIds));
      }
      
      const response = await api.post("/agent", formData);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["chat-history", variables.threadId] });
      queryClient.invalidateQueries({ queryKey: ["project-threads", variables.projectId] });
    }
  });
}

export function useProjectThreads(projectId: string) {
  return useQuery({
    queryKey: ["project-threads", projectId],
    queryFn: async () => {
      const response = await api.get<Thread[]>(`/workspace/projects/${projectId}/threads`);
      return response.data;
    },
    enabled: !!projectId,
  });
}
