import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { Dataset, DatasetFile } from "@/lib/types";
import { getCurrentUser } from "@/lib/auth";

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

export function useUserDatasets(userId: string) {
  return useQuery({
    queryKey: ["users", userId, "datasets"],
    queryFn: async () => {
      const response = await api.get<Dataset[]>("/workspace/datasets", { params: { user_id: userId } });
      return response.data;
    },
    enabled: !!userId,
  });
}

export function useLibraryDatasets() {
  return useQuery({
    queryKey: ["library-datasets"],
    queryFn: async () => {
      const response = await api.get<Dataset[]>("/workspace/library");
      return response.data;
    },
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
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useUpdateDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { datasetId: string; name?: string; description?: string; isPublic?: boolean }) => {
      const formData = new FormData();
      if (data.name) formData.append("name", data.name);
      if (data.description !== undefined) formData.append("description", data.description);
      if (data.isPublic !== undefined) formData.append("is_public", String(data.isPublic));
      
      const response = await api.patch(`/workspace/datasets/${data.datasetId}`, formData);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["datasets", variables.datasetId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["library-datasets"] });
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
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["library-datasets"] });
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
      const user = getCurrentUser();
      const formData = new FormData();
      data.files.forEach(file => formData.append("files", file));
      formData.append("source_type", data.sourceType);
      
      if (user) {
        formData.append("user_id", user.uuid);
      }
      
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

export function useAttachDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { projectId: string; datasetId: string }) => {
      const response = await api.post(`/workspace/projects/${data.projectId}/attachments/${data.datasetId}`);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["projects", variables.projectId, "datasets"] });
    },
  });
}

export function useDetachDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { projectId: string; datasetId: string }) => {
      const response = await api.delete(`/workspace/projects/${data.projectId}/attachments/${data.datasetId}`);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["projects", variables.projectId, "datasets"] });
    },
  });
}

export function useDownloadFile() {
  return useMutation({
    mutationFn: async (fileId: string) => {
      const response = await api.get<{ download_url: string }>('/workspace/files/download', {
        params: { file_id: fileId }
      });
      return response.data.download_url;
    }
  });
}
