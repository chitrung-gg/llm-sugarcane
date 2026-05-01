import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { Dataset, DatasetFile } from "@/lib/types";

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

export function useDatasetFiles(datasetId: string) {
  return useQuery({
    queryKey: ["dataset-files", datasetId],
    queryFn: async () => {
      const response = await api.get<DatasetFile[]>(`/workspace/datasets/${datasetId}/files`);
      return response.data;
    },
    enabled: !!datasetId,
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

export function useUpdateDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { datasetId: string; name?: string; description?: string }) => {
      const formData = new FormData();
      if (data.name) formData.append("name", data.name);
      if (data.description !== undefined) formData.append("description", data.description);
      
      const response = await api.patch(`/workspace/datasets/${data.datasetId}`, formData);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["datasets", variables.datasetId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useDeleteDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (datasetId: string) => {
      const response = await api.delete(`/workspace/datasets/${datasetId}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useDeleteDatasetFile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { fileId: string; datasetId: string }) => {
      const response = await api.delete(`/workspace/datasets/files/${data.fileId}`);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["dataset-files", variables.datasetId] });
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
      queryClient.invalidateQueries({ queryKey: ["dataset-files", variables.datasetId] });
    },
  });
}
