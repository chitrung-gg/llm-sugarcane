import { useCallback } from "react";
import { api } from "@/lib/api-client";

export function useDownload() {
  const downloadFile = useCallback(async (params: { fileId?: string; s3Uri?: string }) => {
    try {
      const response = await api.get<{ download_url: string }>("/workspace/files/download", {
        params: {
          file_id: params.fileId,
          s3_uri: params.s3Uri
        }
      });
      
      const { download_url } = response.data;
      
      // Open in a new tab or trigger download
      const link = document.createElement("a");
      link.href = download_url;
      link.setAttribute("download", ""); // Optional: set filename if possible
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
    } catch (error) {
      console.error("Failed to download file:", error);
      alert("Failed to download file. Please try again.");
    }
  }, []);

  return { downloadFile };
}
