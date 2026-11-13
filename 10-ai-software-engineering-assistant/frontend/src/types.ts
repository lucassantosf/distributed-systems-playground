export type RepositoryStatus = "pending" | "indexing" | "ready" | "error";

export interface CreateRepositoryResponse {
  id: string;
  status: RepositoryStatus;
}

export interface RepositoryResponse {
  id: string;
  github_url: string;
  name: string;
  status: RepositoryStatus;
  created_at: string;
  indexed_at?: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  timestamp?: string;
}

export interface ChatRequestPayload {
  repo_id: string;
  question: string;
}

export interface ChatResponsePayload {
  answer: string;
  sources: string[];
}

