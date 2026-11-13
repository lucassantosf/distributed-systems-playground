import React, { useState, useEffect, useRef } from "react";
import { CreateRepositoryResponse, RepositoryResponse, RepositoryStatus } from "../types";

interface RepoSubmitProps {
  onReady: (repo: { id: string; name: string; url: string }) => void;
}

const GITHUB_URL_REGEX = /^https:\/\/github\.com\/([a-zA-Z0-9_\-\.]+)\/([a-zA-Z0-9_\-\.]+)$/;
const DEFAULT_DEMO_REPO = "https://github.com/navdeep-G/samplemod";
const POLL_INTERVAL_MS = 2000;

export const RepoSubmit: React.FC<RepoSubmitProps> = ({ onReady }) => {
  const [url, setUrl] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [currentRepoId, setCurrentRepoId] = useState<string | null>(null);
  const [status, setStatus] = useState<RepositoryStatus | null>(null);
  const [repoName, setRepoName] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const pollTimerRef = useRef<number | null>(null);

  const clearPolling = () => {
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  useEffect(() => {
    return () => clearPolling();
  }, []);

  const startPolling = (repoId: string, initialName: string, submittedUrl: string) => {
    clearPolling();

    pollTimerRef.current = window.setInterval(async () => {
      try {
        const res = await fetch(`/api/repos/${repoId}`);
        if (!res.ok) {
          if (res.status === 404) {
            throw new Error("Repositório não encontrado no servidor.");
          }
          throw new Error(`Erro ao consultar status no servidor (${res.status}).`);
        }
        const data: RepositoryResponse = await res.json();
        setStatus(data.status);
        if (data.name) setRepoName(data.name);

        if (data.status === "ready") {
          clearPolling();
          setLoading(false);
          window.setTimeout(() => {
            onReady({ id: data.id, name: data.name || initialName, url: submittedUrl });
          }, 800);
        } else if (data.status === "error") {
          clearPolling();
          setLoading(false);
          setError(
            "A ingestão deste repositório falhou. Verifique se o repositório é público e possui arquivos suportados (.py, .ts, .js, .go, etc.)."
          );
        }
      } catch (err) {
        clearPolling();
        setLoading(false);
        setError(
          err instanceof Error
            ? err.message
            : "Erro ao conectar com o servidor durante o acompanhamento."
        );
      }
    }, POLL_INTERVAL_MS);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanUrl = url.trim().replace(/\/+$/, "");
    if (!cleanUrl) {
      setError("Por favor, informe a URL do repositório.");
      return;
    }

    if (!GITHUB_URL_REGEX.test(cleanUrl)) {
      setError("URL inválida. Formato esperado: https://github.com/owner/repo");
      return;
    }

    setLoading(true);
    setStatus("pending");
    setCurrentRepoId(null);

    try {
      const res = await fetch("/api/repos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ github_url: cleanUrl }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        if (res.status === 404) {
          throw new Error("Repositório não encontrado no GitHub. Verifique a URL.");
        } else if (res.status === 429 || res.status === 403) {
          throw new Error("Limite de requisições da API atingido. Aguarde alguns instantes.");
        }
        throw new Error(errData.detail || `Erro ao submeter repositório (${res.status}).`);
      }

      const data: CreateRepositoryResponse = await res.json();
      setCurrentRepoId(data.id);
      setStatus(data.status);

      const derivedName = cleanUrl.split("/").pop() || cleanUrl;
      setRepoName(derivedName);

      startPolling(data.id, derivedName, cleanUrl);
    } catch (err) {
      setLoading(false);
      setStatus(null);
      setError(
        err instanceof Error
          ? err.message
          : "Erro ao conectar com o servidor. Verifique se o backend está em execução."
      );
    }
  };

  const handleReset = () => {
    clearPolling();
    setLoading(false);
    setStatus(null);
    setCurrentRepoId(null);
    setError(null);
  };

  return (
    <div className="card">
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label" htmlFor="repo-url">
            URL do Repositório GitHub
          </label>
          <div className="input-row">
            <input
              id="repo-url"
              type="text"
              className="input-text"
              placeholder="https://github.com/owner/repository"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                if (error) setError(null);
              }}
              disabled={loading}
              autoFocus
            />
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || !url.trim()}
            >
              {loading ? (
                <>
                  <span className="spinner" /> Analisando...
                </>
              ) : (
                "Analisar"
              )}
            </button>
          </div>

          <div className="quick-examples">
            <span>Exemplo rápido:</span>
            <button
              type="button"
              className="chip"
              onClick={() => {
                setUrl(DEFAULT_DEMO_REPO);
                if (error) setError(null);
              }}
              disabled={loading}
            >
              navdeep-G/samplemod
            </button>
          </div>

          {error && (
            <div className="alert-box alert-error">
              <span>⚠️ {error}</span>
              {status === "error" && (
                <button
                  type="button"
                  className="btn btn-sm btn-secondary"
                  onClick={handleReset}
                  style={{ marginLeft: "auto" }}
                >
                  Tentar outro
                </button>
              )}
            </div>
          )}
        </div>
      </form>

      {status && (
        <div className="status-box">
          <div className="status-header">
            <div>
              <strong>{repoName || "Repositório"}</strong>
              {currentRepoId && (
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  ID: <code>{currentRepoId}</code>
                </div>
              )}
            </div>

            {status === "pending" && (
              <span className="status-badge badge-pending">
                <span className="spinner" /> Aguardando...
              </span>
            )}
            {status === "indexing" && (
              <span className="status-badge badge-indexing">
                <span className="spinner" /> Indexando...
              </span>
            )}
            {status === "ready" && (
              <span className="status-badge badge-ready">
                ✓ Pronto
              </span>
            )}
            {status === "error" && (
              <span className="status-badge badge-error">
                ✕ Falhou
              </span>
            )}
          </div>

          {status === "indexing" && (
            <div className="progress-bar-container">
              <div className="progress-bar-indeterminate" />
            </div>
          )}
        </div>
      )}
    </div>
  );
};
