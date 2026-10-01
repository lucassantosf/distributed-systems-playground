import React from 'react';
import { RefreshLog } from '../auth/api';

interface RefreshLogCardProps {
  logs: RefreshLog[];
  onManualRefresh: () => void;
  loading: boolean;
}

export const RefreshLogCard: React.FC<RefreshLogCardProps> = ({
  logs,
  onManualRefresh,
  loading,
}) => {
  return (
    <div className="card" style={{ gridColumn: '1 / -1', borderColor: 'var(--accent-green)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
        <h3 className="card-title" style={{ borderBottom: 'none', marginBottom: 0, color: 'var(--accent-green)' }}>
          🔄 Card 16: Log de Renovação (Refresh Token Automático)
        </h3>
        <button
          className="btn btn-primary"
          style={{ backgroundColor: 'var(--accent-green)', color: '#0f172a', fontSize: '0.85rem' }}
          onClick={onManualRefresh}
          disabled={loading}
        >
          {loading ? 'Renovando...' : '⚡ Forçar Refresh Token Agora'}
        </button>
      </div>

      <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
        Quando o <code>api-simples</code> responde com <strong>HTTP 401 (Unauthorized)</strong> por expiração do Access Token, o cliente executa <code>POST /token</code> com <code>grant_type=refresh_token</code>, atualiza os tokens em memória e repete a chamada sem deslogar o usuário.
      </p>

      {logs.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {logs.map((log, index) => (
            <div
              key={index}
              style={{
                backgroundColor: 'var(--bg-primary)',
                padding: '0.75rem 1rem',
                borderRadius: '6px',
                borderLeft: '4px solid var(--accent-green)',
                fontSize: '0.85rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <strong style={{ color: 'var(--accent-green)' }}>✅ Renovação #{logs.length - index}</strong>
                <span style={{ color: 'var(--text-muted)' }}>{log.timestamp}</span>
              </div>
              <div style={{ marginTop: '0.25rem' }}>
                Motivo: <code>{log.reason}</code>
              </div>
              <div style={{ marginTop: '0.25rem', color: 'var(--text-muted)' }}>
                Novo Access Token: <code>{log.newAccessTokenSnippet}</code>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div
          style={{
            padding: '0.85rem',
            backgroundColor: 'var(--bg-primary)',
            borderRadius: '6px',
            color: 'var(--text-muted)',
            fontSize: '0.85rem',
            textAlign: 'center',
          }}
        >
          Nenhum refresh executado nesta sessão ainda. Clique em "Forçar Refresh Token Agora" para testar a renovação.
        </div>
      )}
    </div>
  );
};
