import React from 'react';

interface AuthStateCardProps {
  isAuthenticated: boolean;
  userClaims?: Record<string, unknown> | null;
}

export const AuthStateCard: React.FC<AuthStateCardProps> = ({
  isAuthenticated,
  userClaims,
}) => {
  return (
    <div className="card">
      <h3 className="card-title">🔐 Estado de Autenticação</h3>

      <div className="info-group">
        <div className="info-label">Status da Sessão</div>
        <div className="info-value">
          {isAuthenticated ? (
            <span style={{ color: 'var(--accent-green)' }}>
              🟢 Sessão Ativa — Token Presente
            </span>
          ) : (
            <span style={{ color: 'var(--accent-red)' }}>
              🔴 Nenhuma sessão ativa. Clique em "Entrar" para iniciar o fluxo PKCE.
            </span>
          )}
        </div>
      </div>

      <div className="info-group">
        <div className="info-label">Client ID</div>
        <div className="info-value">
          <code>frontend-pkce</code> (Public Client)
        </div>
      </div>

      {isAuthenticated && userClaims && (
        <div className="info-group" style={{ marginTop: '1rem' }}>
          <div className="info-label">Claims do Usuário (ID Token / Access Token)</div>
          <pre>{JSON.stringify(userClaims, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};
