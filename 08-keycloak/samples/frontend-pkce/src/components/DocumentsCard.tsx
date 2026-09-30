import React from 'react';

interface DocumentsCardProps {
  isAuthenticated: boolean;
}

export const DocumentsCard: React.FC<DocumentsCardProps> = ({
  isAuthenticated,
}) => {
  return (
    <div className="card">
      <h3 className="card-title">📄 Lista de Documentos</h3>

      <div className="info-group">
        <div className="info-label">Integração com Backend (/api/documents)</div>
        <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>
          Esta seção exibirá os documentos retornados pelo <code>api-simples</code> (porta 8001) via proxy <code>/api</code>.
        </p>
      </div>

      {!isAuthenticated ? (
        <div
          style={{
            padding: '1rem',
            backgroundColor: 'rgba(248, 113, 113, 0.1)',
            border: '1px dashed var(--accent-red)',
            borderRadius: '6px',
            marginTop: '1rem',
            fontSize: '0.9rem',
          }}
        >
          🔒 Faça login para carregar os documentos protegidos por Bearer Token.
        </div>
      ) : (
        <div
          style={{
            padding: '1rem',
            backgroundColor: 'rgba(74, 222, 128, 0.1)',
            border: '1px dashed var(--accent-green)',
            borderRadius: '6px',
            marginTop: '1rem',
            fontSize: '0.9rem',
          }}
        >
          ✅ Usuário autenticado. Pronto para fazer chamadas Bearer para a API (cards seguintes).
        </div>
      )}
    </div>
  );
};
