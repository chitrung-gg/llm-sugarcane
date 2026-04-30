import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { Dataset } from "@/lib/types";

export function useProjectDatasets(projectId: string) {
  return useQuery({
    queryKey: ["projects", projectId, "datasets"],
    queryFn: async () => {
      const response = await api.get<Dataset[]>(`/workspace/projects/${projectId}/datasets`);
      return response.data;
    },
    enabled: !!projectId,
  });
}

export function useDataset(id: string) {
  return useQuery({
    queryKey: ["datasets", id],
    queryFn: async () => {
      const response = await api.get<Dataset>(`/workspace/datasets/${id}`);
      return response.data;
    },
    enabled: !!id,
  });
}

export function useCreateDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { projectId: string; name: string; description?: string }) => {
      const formData = new FormData();
      formData.append("name", data.name);
      if (data.description) {
        formData.append("description", data.description);
      }
      const response = await api.post<Dataset>(`/workspace/projects/${data.projectId}/datasets`, formData);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["projects", variables.projectId, "datasets"] });
    },
  });
}

export function useUploadDatasetFiles() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { 
      datasetId: string; 
      files: File[]; 
      sourceType: string;
    }) => {
      const formData = new FormData();
      data.files.forEach(file => formData.append("files", file));
      formData.append("source_type", data.sourceType);
      
      const response = await api.post(`/workspace/datasets/${data.datasetId}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["datasets", variables.datasetId] });
    },
  });
}
