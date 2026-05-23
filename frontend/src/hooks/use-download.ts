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

      // Open in a new tab — the `download` attribute is ignored for cross-origin URLs
      // (e.g. S3 presigned URLs), so a direct click would navigate the current page away.
      window.open(download_url, "_blank", "noopener,noreferrer");
      
    } catch (error) {
      console.error("Failed to download file:", error);
      alert("Failed to download file. Please try again.");
    }
  }, []);

  return { downloadFile };
}
