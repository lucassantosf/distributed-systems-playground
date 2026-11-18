import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  ChatMessage,
  ChatResponsePayload,
  ConversationDetail,
  ConversationMessageItem,
} from "../types";
import { ConversationSidebar } from "./ConversationSidebar";

interface ChatViewProps {
  repoId: string;
  repoName: string;
  githubUrl: string;
  initialConversationId?: string;
  onBack: () => void;
}

const SUGGESTED_QUESTIONS = [
  "Qual é a estrutura principal e o propósito deste repositório?",
  "Quais são os principais módulos e o que cada um faz?",
  "Como funcionam os testes ou como rodar o projeto?",
];

const WELCOME_MSG = (repoName: string): ChatMessage => ({
  id: "welcome",
  role: "assistant",
  content: `Olá! Sou seu assistente de engenharia para o repositório **${repoName}**.\nPergunte qualquer coisa sobre a arquitetura, regras de negócio, funções ou testes deste código!`,
});

function conversationMsgToChatMsg(m: ConversationMessageItem): ChatMessage {
  return {
    id: m.id,
    role: m.role as "user" | "assistant",
    content: m.content,
    sources: m.sources,
    timestamp: m.created_at,
  };
}

export const ChatView: React.FC<ChatViewProps> = ({
  repoId,
  repoName,
  githubUrl,
  initialConversationId,
  onBack,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MSG(repoName)]);
  const [input, setInput] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [loadingSeconds, setLoadingSeconds] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [lastFailedQuestion, setLastFailedQuestion] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // F2-2: estado de conversa
  const [conversationId, setConversationId] = useState<string | null>(
    initialConversationId || null
  );
  const [sidebarRefresh, setSidebarRefresh] = useState(0);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  useEffect(() => {
    if (!loading) {
      setLoadingSeconds(0);
      return;
    }
    const interval = setInterval(() => {
      setLoadingSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [loading]);

  const getLoadingMessage = (seconds: number) => {
    if (seconds < 3) return "Consultando vetores e arquivos relevantes...";
    if (seconds < 7) return "Sintetizando resposta com modelo de IA...";
    return "Processando análise detalhada do código...";
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // F2-2: carregar conversa existente da sidebar
  const handleSelectConversation = useCallback(async (id: string) => {
    if (id === conversationId) return;
    try {
      const res = await fetch(`/api/conversations/${id}`);
      if (!res.ok) return;
      const conv: ConversationDetail = await res.json();
      const loaded: ChatMessage[] = conv.messages.map(conversationMsgToChatMsg);
      setMessages(loaded.length > 0 ? loaded : [WELCOME_MSG(repoName)]);
      setConversationId(id);
      setError(null);
      setLastFailedQuestion(null);
    } catch {
      // mantém estado atual se falhar
    }
  }, [conversationId, repoName]);

  // F2-2: iniciar conversa nova
  const handleNewConversation = useCallback(() => {
    setConversationId(null);
    setMessages([WELCOME_MSG(repoName)]);
    setError(null);
    setLastFailedQuestion(null);
    inputRef.current?.focus();
  }, [repoName]);

  // F2-2: carregar conversa inicial se fornecida
  useEffect(() => {
    if (initialConversationId) {
      handleSelectConversation(initialConversationId);
    }
  }, [initialConversationId, handleSelectConversation]);

  const handleSend = async (questionToSend?: string) => {
    const question = (questionToSend || input).trim();
    if (!question || loading) return;

    setError(null);
    setLastFailedQuestion(null);
    setInput("");

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: question,
    };

    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);
    const startTime = performance.now();

    try {
      const body: Record<string, unknown> = {
        repo_id: repoId,
        question: question,
      };
      if (conversationId) {
        body.conversation_id = conversationId;
      }

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        if (res.status === 404) {
          throw new Error(
            "Repositório não encontrado no sistema. Ele pode ter sido removido."
          );
        } else if (res.status === 409) {
          throw new Error(
            "O repositório ainda não concluiu a indexação. Aguarde o status ficar pronto."
          );
        } else if (res.status === 503) {
          throw new Error(
            "O modelo de IA está temporariamente com alta demanda. Tente novamente em instantes."
          );
        }
        throw new Error(
          errorData.detail || `Erro na resposta do chat (${res.status}).`
        );
      }

      const data: ChatResponsePayload = await res.json();
      const elapsed = parseFloat(((performance.now() - startTime) / 1000).toFixed(1));

      // F2-2: captura o conversation_id retornado pelo backend
      if (data.conversation_id && !conversationId) {
        setConversationId(data.conversation_id);
        // Força recarga da lista de conversas na sidebar
        setSidebarRefresh((n) => n + 1);
      }

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: data.answer,
        sources: data.sources,
        latencySeconds: elapsed,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setLastFailedQuestion(question);
      setError(
        err instanceof Error
          ? err.message
          : "Erro ao conectar com o servidor. Verifique sua conexão e tente novamente."
      );
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClearChat = () => {
    setMessages([WELCOME_MSG(repoName)]);
    setConversationId(null);
    setError(null);
    setLastFailedQuestion(null);
  };

  return (
    <div className="chat-layout">
      {/* F2-2: Sidebar de conversas */}
      <ConversationSidebar
        repoId={repoId}
        activeConversationId={conversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        refreshTrigger={sidebarRefresh}
      />

      {/* Área principal do chat */}
      <div className="chat-container">
        {/* Barra superior de contexto */}
        <div className="active-repo-bar">
          <div className="active-repo-info">
            <span className="status-badge badge-ready">✓ Conectado</span>
            <span className="repo-name">{repoName}</span>
            <span className="repo-url-label">({githubUrl})</span>
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            {messages.length > 1 && (
              <button
                className="btn btn-sm btn-secondary"
                onClick={handleClearChat}
                title="Limpar mensagens"
              >
                Limpar chat
              </button>
            )}
            <button className="btn btn-sm btn-secondary" onClick={onBack}>
              Trocar Repositório
            </button>
          </div>
        </div>

        {/* Área de mensagens com scroll */}
        <div className="chat-messages-box">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`chat-bubble-row ${
                msg.role === "user" ? "row-user" : "row-assistant"
              }`}
            >
              <div
                className={`chat-bubble ${
                  msg.role === "user" ? "bubble-user" : "bubble-assistant"
                }`}
              >
                <div className="bubble-content">{msg.content}</div>

                {msg.sources && msg.sources.length > 0 && (
                  <div className="sources-container">
                    <span className="sources-title">
                      Fontes consultadas ({msg.sources.length}):
                    </span>
                    <div className="sources-chips">
                      {msg.sources.map((src, i) => (
                        <span key={i} className="source-chip" title={src}>
                          📄 {src}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {msg.role === "assistant" && msg.id !== "welcome" && (
                  <div className="bubble-footer">
                    {msg.latencySeconds !== undefined && (
                      <span className="latency-badge" title="Tempo de resposta">
                        ⚡ {msg.latencySeconds}s
                      </span>
                    )}
                    <button
                      type="button"
                      className="copy-btn"
                      onClick={() => handleCopy(msg.id, msg.content)}
                      title="Copiar resposta"
                    >
                      {copiedId === msg.id ? "✓ Copiado" : "📋 Copiar"}
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="chat-bubble-row row-assistant">
              <div className="chat-bubble bubble-assistant loading-bubble">
                <span className="spinner" />
                <div className="loading-content">
                  <span className="loading-text">
                    {getLoadingMessage(loadingSeconds)}
                  </span>
                  <span className="loading-timer-badge">{loadingSeconds}s</span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Sugestões rápidas no início */}
        {messages.length === 1 && !loading && (
          <div className="suggested-questions-box">
            <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              Perguntas sugeridas:
            </span>
            <div className="suggested-chips">
              {SUGGESTED_QUESTIONS.map((q, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="chip suggested-chip"
                  onClick={() => handleSend(q)}
                  disabled={loading}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Banner de erro com ação de retry */}
        {error && (
          <div className="alert-box alert-error" style={{ marginTop: "0.75rem" }}>
            <span>⚠️ {error}</span>
            {lastFailedQuestion && (
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                onClick={() => handleSend(lastFailedQuestion)}
                style={{ marginLeft: "auto" }}
              >
                Tentar novamente
              </button>
            )}
          </div>
        )}

        {/* Campo de input */}
        <div className="chat-input-bar">
          <input
            ref={inputRef}
            type="text"
            className="input-text chat-input"
            placeholder="Faça uma pergunta sobre o código deste repositório... (Pressione Enter)"
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              if (error) setError(null);
            }}
            onKeyDown={handleKeyDown}
            disabled={loading}
            autoFocus
          />
          <button
            className="btn btn-primary"
            onClick={() => handleSend()}
            disabled={loading || !input.trim()}
          >
            {loading ? (
              <>
                <span className="spinner" /> Enviando...
              </>
            ) : (
              "Enviar"
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
