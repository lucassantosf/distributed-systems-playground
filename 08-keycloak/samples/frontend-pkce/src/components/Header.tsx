import React from 'react';

interface HeaderProps {
  isAuthenticated: boolean;
  username?: string;
  onLogin: () => void;
  onLogout: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  isAuthenticated,
  username,
  onLogin,
  onLogout,
}) => {
  return (
    <header>
      <div>
        <h2>Sample B — Frontend PKCE</h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          OAuth2 Authorization Code Flow + PKCE (Single Page Application)
        </p>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <span
          className={`badge ${
            isAuthenticated ? 'badge-authenticated' : 'badge-unauthenticated'
          }`}
        >
          {isAuthenticated ? `Autenticado (${username || 'Usuário'})` : 'Não Autenticado'}
        </span>

        {isAuthenticated ? (
          <button className="btn btn-danger" onClick={onLogout}>
            Sair (Logout)
          </button>
        ) : (
          <button className="btn btn-primary" onClick={onLogin}>
            Entrar (Login PKCE)
          </button>
        )}
      </div>
    </header>
  );
};
