export interface Project {
  id: string;
  name: string;
  description?: string;
  dataset_metadata?: Record<string, unknown>;
  created_at: string;
}

export interface Dataset {
  id: string;
  project_id: string;
  name: string;
  description?: string;
  dataset_metadata?: Record<string, unknown>;
  files?: DatasetFile[];
}

export interface DatasetFile {
  id: string;
  dataset_id: string;
  file_id: string;
  file_name: string;
  file_type: string;
  rustfs_uri: string;
  file_metadata?: Record<string, unknown>;
  created_at: string;
}

export interface Thread {
  id: string;
  project_id: string;
  title: string;
  created_at: string;
}
