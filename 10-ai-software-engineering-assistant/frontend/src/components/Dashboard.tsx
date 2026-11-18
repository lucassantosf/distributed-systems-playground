import React, { useState, useEffect, useCallback } from "react";
import { RepositoryResponse, ConversationListItem } from "../types";

interface DashboardProps {
  onOpenChat: (repo: { id: string; name: string; url: string }, conversationId?: string) => void;
  onAddNew: () => void;
  refreshTrigger: number;
}

interface RepoWithConversations {
  repo: RepositoryResponse;
  conversations: ConversationListItem[];
  loadingConvs: boolean;
  expanded: boolean;
}

export const Dashboard: React.FC<DashboardProps> = ({
  onOpenChat,
  onAddNew,
  refreshTrigger,
}) => {
  const [items, setItems] = useState<RepoWithConversations[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRepos = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/repos");
      if (!res.ok) throw new Error(`Erro ao carregar repositórios (${res.status})`);
      const repos: RepositoryResponse[] = await res.json();
      setItems(
        repos.map((repo) => ({
          repo,
          conversations: [],
          loadingConvs: false,
          expanded: false,
        }))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar repositórios.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRepos();
  }, [fetchRepos, refreshTrigger]);

  const toggleExpand = async (repoId: string) => {
    setItems((prev) =>
      prev.map((item) => {
        if (item.repo.id !== repoId) return item;
        const willExpand = !item.expanded;
        if (willExpand && item.conversations.length === 0) {
          // carrega conversas ao expandir pela primeira vez
          loadConversations(repoId);
        }
        return { ...item, expanded: willExpand };
      })
    );
  };

  const loadConversations = async (repoId: string) => {
    setItems((prev) =>
      prev.map((item) =>
        item.repo.id === repoId ? { ...item, loadingConvs: true } : item
      )
    );
    try {
      const res = await fetch(`/api/repos/${repoId}/conversations`);
      const convs: ConversationListItem[] = res.ok ? await res.json() : [];
      setItems((prev) =>
        prev.map((item) =>
          item.repo.id === repoId
            ? { ...item, conversations: convs, loadingConvs: false }
            : item
        )
      );
    } catch {
      setItems((prev) =>
        prev.map((item) =>
          item.repo.id === repoId ? { ...item, loadingConvs: false } : item
        )
      );
    }
  };

  const formatDate = (iso: string | null | undefined) => {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const statusBadge = (status: string) => {
    const map: Record<string, { cls: string; label: string }> = {
      ready:    { cls: "badge-ready",    label: "✓ Pronto" },
      indexing: { cls: "badge-indexing", label: "⟳ Indexando" },
      pending:  { cls: "badge-pending",  label: "⏳ Aguardando" },
      error:    { cls: "badge-error",    label: "✕ Erro" },
    };
    const s = map[status] ?? { cls: "badge-pending", label: status };
    return <span className={`status-badge ${s.cls}`}>{s.label}</span>;
  };

  if (loading) {
    return (
      <div className="dashboard-loading">
        <span className="spinner" />
        <span>Carregando repositórios...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert-box alert-error" style={{ marginTop: "1rem" }}>
        ⚠️ {error}
        <button className="btn btn-sm btn-secondary" onClick={fetchRepos} style={{ marginLeft: "auto" }}>
          Tentar novamente
        </button>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <div>
          <h2 className="dashboard-title">Seus Repositórios</h2>
          <p className="dashboard-subtitle">
            {items.length === 0
              ? "Nenhum repositório ainda. Comece adicionando um abaixo."
              : `${items.length} repositório${items.length > 1 ? "s" : ""} cadastrado${items.length > 1 ? "s" : ""}`}
          </p>
        </div>
        <button className="btn btn-primary" onClick={onAddNew}>
          + Novo Repositório
        </button>
      </div>

      {items.length === 0 ? (
        <div className="dashboard-empty">
          <div className="dashboard-empty-icon">🗂️</div>
          <p>Adicione um repositório do GitHub para começar a conversar sobre o código.</p>
          <button className="btn btn-primary" onClick={onAddNew}>
            Adicionar meu primeiro repositório
          </button>
        </div>
      ) : (
        <div className="repo-list">
          {items.map(({ repo, conversations, loadingConvs, expanded }) => (
            <div key={repo.id} className="repo-card">
              {/* Cabeçalho do repositório */}
              <div className="repo-card-header">
                <div className="repo-card-info">
                  <span className="repo-card-name">{repo.name}</span>
                  <a
                    href={repo.github_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="repo-card-url"
                  >
                    {repo.github_url}
                  </a>
                  <span className="repo-card-date">
                    Indexado em {formatDate(repo.indexed_at ?? repo.created_at)}
                  </span>
                </div>
                <div className="repo-card-actions">
                  {statusBadge(repo.status)}
                  {repo.status === "ready" && (
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => onOpenChat({ id: repo.id, name: repo.name, url: repo.github_url })}
                    >
                      Nova Conversa
                    </button>
                  )}
                  <button
                    className="btn btn-sm btn-secondary repo-expand-btn"
                    onClick={() => toggleExpand(repo.id)}
                    title={expanded ? "Ocultar histórico" : "Ver histórico"}
                  >
                    {expanded ? "▲ Histórico" : "▼ Histórico"}
                  </button>
                </div>
              </div>

              {/* Histórico de conversas expandível */}
              {expanded && (
                <div className="repo-conv-list">
                  {loadingConvs && (
                    <div className="repo-conv-loading">
                      <span className="spinner" /> Carregando conversas...
                    </div>
                  )}
                  {!loadingConvs && conversations.length === 0 && (
                    <div className="repo-conv-empty">
                      Nenhuma conversa ainda para este repositório.
                    </div>
                  )}
                  {!loadingConvs &&
                    conversations.map((conv) => (
                      <button
                        key={conv.id}
                        className="repo-conv-item"
                        onClick={() =>
                          onOpenChat(
                            { id: repo.id, name: repo.name, url: repo.github_url },
                            conv.id
                          )
                        }
                      >
                        <span className="repo-conv-title">💬 {conv.title}</span>
                        <span className="repo-conv-date">
                          {formatDate(conv.updated_at)}
                        </span>
                      </button>
                    ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
