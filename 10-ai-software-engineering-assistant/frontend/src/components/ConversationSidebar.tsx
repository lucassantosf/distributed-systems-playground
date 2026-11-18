import React, { useEffect, useState, useCallback } from "react";
import { ConversationListItem } from "../types";

interface ConversationSidebarProps {
  repoId: string;
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  refreshTrigger: number; // incrementar para forçar reload da lista
}

export const ConversationSidebar: React.FC<ConversationSidebarProps> = ({
  repoId,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  refreshTrigger,
}) => {
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchConversations = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/repos/${repoId}/conversations`);
      if (res.ok) {
        const data: ConversationListItem[] = await res.json();
        setConversations(data);
      }
    } catch {
      // silencioso — a sidebar não bloqueia o chat
    } finally {
      setLoading(false);
    }
  }, [repoId]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations, refreshTrigger]);

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return "agora";
    if (diffMin < 60) return `${diffMin}min atrás`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return `${diffH}h atrás`;
    return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  };

  return (
    <aside className="conversation-sidebar">
      <div className="sidebar-header">
        <span className="sidebar-title">Conversas</span>
        <button
          className="btn btn-sm btn-primary sidebar-new-btn"
          onClick={onNewConversation}
          title="Iniciar nova conversa"
        >
          + Nova
        </button>
      </div>

      <div className="sidebar-list">
        {loading && conversations.length === 0 && (
          <div className="sidebar-empty">Carregando...</div>
        )}
        {!loading && conversations.length === 0 && (
          <div className="sidebar-empty">Nenhuma conversa ainda.</div>
        )}
        {conversations.map((conv) => (
          <button
            key={conv.id}
            className={`sidebar-item ${activeConversationId === conv.id ? "sidebar-item-active" : ""}`}
            onClick={() => onSelectConversation(conv.id)}
            title={conv.title}
          >
            <span className="sidebar-item-title">{conv.title}</span>
            <span className="sidebar-item-date">{formatDate(conv.updated_at)}</span>
          </button>
        ))}
      </div>
    </aside>
  );
};
