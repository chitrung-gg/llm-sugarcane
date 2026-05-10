export interface Project {
  id: string;
  owner_id: string;
  name: string;
  description?: string;
  dataset_metadata?: Record<string, unknown>;
  created_at: string;
}

export interface Thread {
  id: string;
  project_id: string;
  title: string;
  created_at: string;
  updated_at?: string;
}

export interface Dataset {
  id: string;
  project_id: string;
  name: string;
  description?: string;
  dataset_metadata?: Record<string, unknown>;
  is_public: boolean;
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

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  type?: "answer" | "thought" | "error" | "interrupt";
  execution_id?: string;
  thoughts?: string[];
  rag_sources?: RAGSource[];
  web_results?: WebResult[];
  tool_executions?: ToolExecution[];
  interrupt_data?: Record<string, unknown>;
}

export interface RAGSource {
  source_file: string;
  chunks_used: number;
  highest_score: number | null;
}

export interface WebResult {
  title: string;
  link: string;
  snippet: string;
}

export interface ToolExecution {
  tool_name: string;
  status: string;
  output: string;
}

export interface ChatHistory {
  thread_id: string;
  messages: {
    id: string;
    role: "user" | "assistant";
    content: string;
    type?: "answer" | "thought" | "error";
    execution_id?: string;
  }[];
  rag_results: Record<string, unknown>[];
  tool_results: Record<string, unknown>[];
  web_results: WebResult[];
  summary?: string;
}

export interface IngestionStatus {
  task_id: string;
  status: "PENDING" | "STARTED" | "PROGRESS" | "SUCCESS" | "FAILURE";
  ready: boolean;
  meta?: {
    current?: number;
    total?: number;
    percent?: number;
    message?: string;
  };
}
