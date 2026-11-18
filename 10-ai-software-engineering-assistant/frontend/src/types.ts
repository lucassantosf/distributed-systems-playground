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
  latencySeconds?: number;
}

export interface ChatRequestPayload {
  repo_id: string;
  question: string;
  conversation_id?: string;   // F2-2: opcional, omitir para nova conversa
}

export interface ChatResponsePayload {
  answer: string;
  sources: string[];
  conversation_id: string;    // F2-2: sempre retornado pelo backend
}

// F2-2: Conversa
export interface ConversationListItem {
  id: string;
  repo_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: string[];
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  repo_id: string;
  title: string;
  messages: ConversationMessageItem[];
  created_at: string;
  updated_at: string;
}
