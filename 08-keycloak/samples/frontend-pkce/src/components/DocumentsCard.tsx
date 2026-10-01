import React, { useEffect, useState, useCallback } from 'react';
import { TokenResponse } from '../auth/tokens';
import { fetchWithAuth, RefreshLog } from '../auth/api';

interface DocumentItem {
  id: number;
  title: string;
  content: string;
  owner_id: string;
}

interface DocumentsCardProps {
  isAuthenticated: boolean;
  tokens: TokenResponse | null;
  userRoles?: string[];
  onTokensRefreshed: (newTokens: TokenResponse, log: RefreshLog) => void;
}

export const DocumentsCard: React.FC<DocumentsCardProps> = ({
  isAuthenticated,
  tokens,
  userRoles = [],
  onTokensRefreshed,
}) => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [statusCode, setStatusCode] = useState<number | null>(null);

  const [newTitle, setNewTitle] = useState<string>('');
  const [newContent, setNewContent] = useState<string>('');
  const [creating, setCreating] = useState<boolean>(false);

  const fetchDocuments = useCallback(async () => {
    if (!isAuthenticated || !tokens?.access_token) {
      setDocuments([]);
      setErrorMsg(null);
      setStatusCode(null);
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    setStatusCode(null);

    try {
      // Utiliza fetchWithAuth com auto-refresh token (Card 16)
      const response = await fetchWithAuth(
        '/api/documents',
        {},
        tokens,
        onTokensRefreshed
      );

      setStatusCode(response.status);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const detail = errorData.detail || `Erro HTTP ${response.status}`;
        setErrorMsg(detail);
        setDocuments([]);
      } else {
        const data = await response.json();
        setDocuments(data);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(`Erro de conexão com a API: ${msg}`);
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, tokens, onTokensRefreshed]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleCreateDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newContent.trim() || !tokens?.access_token) return;

    setCreating(true);
    setErrorMsg(null);

    try {
      const response = await fetchWithAuth(
        '/api/documents',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            title: newTitle,
            content: newContent,
          }),
        },
        tokens,
        onTokensRefreshed
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        setErrorMsg(errorData.detail || `Erro ao criar (HTTP ${response.status})`);
      } else {
        setNewTitle('');
        setNewContent('');
        await fetchDocuments();
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(`Erro de conexão: ${msg}`);
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteDocument = async (docId: number) => {
    if (!tokens?.access_token) return;

    try {
      const response = await fetchWithAuth(
        `/api/documents/${docId}`,
        { method: 'DELETE' },
        tokens,
        onTokensRefreshed
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        alert(errorData.detail || `Erro ao deletar (HTTP ${response.status})`);
      } else {
        await fetchDocuments();
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(`Erro ao deletar: ${msg}`);
    }
  };

  const isAdmin = userRoles.includes('admin');
  const canCreate = userRoles.includes('admin') || userRoles.includes('editor');

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
        <h3 className="card-title" style={{ borderBottom: 'none', marginBottom: 0 }}>
          📄 Card 15 & 16: Documentos Protegidos por JWT
        </h3>
        {isAuthenticated && (
          <button
            className="btn btn-primary"
            style={{ fontSize: '0.85rem', padding: '0.35rem 0.75rem' }}
            onClick={fetchDocuments}
            disabled={loading}
          >
            {loading ? 'Carregando...' : '🔄 Recarregar'}
          </button>
        )}
      </div>

      {!isAuthenticated ? (
        <div
          style={{
            padding: '1rem',
            backgroundColor: 'rgba(248, 113, 113, 0.1)',
            border: '1px dashed var(--accent-red)',
            borderRadius: '6px',
            fontSize: '0.9rem',
          }}
        >
          🔒 Faça login para carregar os documentos protegidos por Bearer Token da <code>api-simples</code>.
        </div>
      ) : (
        <div>
          {statusCode && (
            <div style={{ marginBottom: '1rem', fontSize: '0.85rem' }}>
              Status HTTP da API:{' '}
              <span
                className={`badge ${
                  statusCode === 200 || statusCode === 201
                    ? 'badge-authenticated'
                    : 'badge-unauthenticated'
                }`}
              >
                HTTP {statusCode} {statusCode === 200 ? 'OK' : statusCode === 403 ? 'Forbidden' : statusCode === 401 ? 'Unauthorized' : ''}
              </span>
            </div>
          )}

          {errorMsg && (
            <div
              style={{
                padding: '0.85rem 1rem',
                backgroundColor: 'rgba(248, 113, 113, 0.15)',
                border: '1px solid var(--accent-red)',
                borderRadius: '6px',
                color: 'var(--accent-red)',
                marginBottom: '1rem',
                fontSize: '0.9rem',
              }}
            >
              ⚠️ {errorMsg}
            </div>
          )}

          {documents.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  style={{
                    backgroundColor: 'var(--bg-primary)',
                    padding: '0.85rem 1rem',
                    borderRadius: '6px',
                    border: '1px solid var(--border-color)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <h4 style={{ color: 'var(--accent-blue)', fontSize: '1rem' }}>
                      #{doc.id} — {doc.title}
                    </h4>
                    {isAdmin && (
                      <button
                        className="btn btn-danger"
                        style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                        onClick={() => handleDeleteDocument(doc.id)}
                      >
                        Deletar
                      </button>
                    )}
                  </div>
                  <p style={{ fontSize: '0.9rem', marginTop: '0.35rem' }}>{doc.content}</p>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
                    owner_id: <code>{doc.owner_id}</code>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            !loading && !errorMsg && (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                Nenhum documento retornado para o seu perfil.
              </p>
            )
          )}

          {canCreate && (
            <form
              onSubmit={handleCreateDocument}
              style={{
                marginTop: '1.5rem',
                paddingTop: '1rem',
                borderTop: '1px solid var(--border-color)',
              }}
            >
              <h4 style={{ fontSize: '0.95rem', color: 'var(--accent-green)', marginBottom: '0.75rem' }}>
                ➕ Criar Novo Documento (Exige role editor ou admin)
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <input
                  type="text"
                  placeholder="Título do documento"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  style={{
                    padding: '0.5rem',
                    backgroundColor: 'var(--bg-primary)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)',
                    borderRadius: '4px',
                  }}
                  required
                />
                <textarea
                  placeholder="Conteúdo do documento"
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  style={{
                    padding: '0.5rem',
                    backgroundColor: 'var(--bg-primary)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)',
                    borderRadius: '4px',
                    minHeight: '60px',
                  }}
                  required
                />
                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ backgroundColor: 'var(--accent-green)', color: '#0f172a', alignSelf: 'flex-start' }}
                  disabled={creating}
                >
                  {creating ? 'Salvando...' : 'Salvar Documento'}
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
};
