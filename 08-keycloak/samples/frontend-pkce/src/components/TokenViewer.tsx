import React, { useState } from 'react';
import { TokenResponse, decodeJWT, DecodedJWT } from '../auth/tokens';

interface TokenViewerProps {
  tokens: TokenResponse;
}

function formatTimestamp(ts?: unknown): string {
  if (typeof ts !== 'number') return 'N/A';
  const date = new Date(ts * 1000);
  return `${ts} (${date.toLocaleDateString()} ${date.toLocaleTimeString()})`;
}

export const TokenViewer: React.FC<TokenViewerProps> = ({ tokens }) => {
  const [activeTab, setActiveTab] = useState<'access' | 'id' | 'refresh'>('access');
  const [viewMode, setViewMode] = useState<'formatted' | 'raw'>('formatted');

  const decodedAccess = decodeJWT(tokens.access_token);
  const decodedId = tokens.id_token ? decodeJWT(tokens.id_token) : null;
  const decodedRefresh = tokens.refresh_token ? decodeJWT(tokens.refresh_token) : null;

  const getActiveDecoded = (): DecodedJWT | null => {
    if (activeTab === 'access') return decodedAccess;
    if (activeTab === 'id') return decodedId;
    return decodedRefresh;
  };

  const currentDecoded = getActiveDecoded();
  const payload = currentDecoded?.payload || {};

  const roles: string[] =
    (payload.realm_access as { roles?: string[] })?.roles || [];
  const customRoles = roles.filter(
    (r) => !['default-roles-distributed-systems', 'offline_access', 'uma_authorization'].includes(r)
  );

  return (
    <div className="card" style={{ gridColumn: '1 / -1', borderColor: 'var(--accent-blue)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h3 className="card-title" style={{ borderBottom: 'none', marginBottom: 0, color: 'var(--accent-blue)' }}>
          🔍 Card 14: Inspetor Didático de Claims do JWT
        </h3>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            className={`btn ${viewMode === 'formatted' ? 'btn-primary' : ''}`}
            style={{ fontSize: '0.85rem', padding: '0.35rem 0.75rem', backgroundColor: viewMode === 'formatted' ? 'var(--accent-blue)' : 'var(--bg-card)' }}
            onClick={() => setViewMode('formatted')}
          >
            📊 Visão Formatada
          </button>
          <button
            className={`btn ${viewMode === 'raw' ? 'btn-primary' : ''}`}
            style={{ fontSize: '0.85rem', padding: '0.35rem 0.75rem', backgroundColor: viewMode === 'raw' ? 'var(--accent-blue)' : 'var(--bg-card)' }}
            onClick={() => setViewMode('raw')}
          >
            {'{ }'} JSON Bruto
          </button>
        </div>
      </div>

      {/* Abas de Seleção do Token */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
        <button
          className="btn"
          style={{
            backgroundColor: activeTab === 'access' ? 'var(--accent-blue)' : 'var(--bg-card)',
            color: activeTab === 'access' ? '#0f172a' : 'var(--text-primary)',
          }}
          onClick={() => setActiveTab('access')}
        >
          🔑 Access Token (Autorização API)
        </button>
        {tokens.id_token && (
          <button
            className="btn"
            style={{
              backgroundColor: activeTab === 'id' ? 'var(--accent-blue)' : 'var(--bg-card)',
              color: activeTab === 'id' ? '#0f172a' : 'var(--text-primary)',
            }}
            onClick={() => setActiveTab('id')}
          >
            🪪 ID Token (Perfil/Identidade)
          </button>
        )}
        {tokens.refresh_token && (
          <button
            className="btn"
            style={{
              backgroundColor: activeTab === 'refresh' ? 'var(--accent-blue)' : 'var(--bg-card)',
              color: activeTab === 'refresh' ? '#0f172a' : 'var(--text-primary)',
            }}
            onClick={() => setActiveTab('refresh')}
          >
            🔄 Refresh Token (Renovação)
          </button>
        )}
      </div>

      {/* Caixa Didática de Diferenças */}
      <div
        style={{
          padding: '0.85rem 1rem',
          backgroundColor: 'rgba(56, 189, 248, 0.1)',
          borderLeft: '4px solid var(--accent-blue)',
          borderRadius: '4px',
          marginBottom: '1.25rem',
          fontSize: '0.85rem',
        }}
      >
        {activeTab === 'access' && (
          <p>
            <strong>🎯 Papel do Access Token:</strong> Enviado para a API no header <code>Authorization: Bearer</code>. Contém o campo <code>realm_access.roles</code> para o backend decidir o que o usuário pode fazer (RBAC).
          </p>
        )}
        {activeTab === 'id' && (
          <p>
            <strong>👤 Papel do ID Token:</strong> Usado <u>apenas pelo Frontend</u> para exibir a foto, e-mail e nome do usuário na tela. <strong>NUNCA envie o ID Token para as APIs de backend!</strong>
          </p>
        )}
        {activeTab === 'refresh' && (
          <p>
            <strong>🔄 Papel do Refresh Token:</strong> Token de longa duração (30 min) usado exclusivamente com o Keycloak para obter um novo Access Token quando este expirar (5 min).
          </p>
        )}
      </div>

      {/* Conteúdo: Visão Formatada vs JSON Bruto */}
      {viewMode === 'formatted' ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <div className="info-group">
            <div className="info-label">sub (Subject / ID do Usuário)</div>
            <div className="info-value"><code>{(payload.sub as string) || 'N/A'}</code></div>
          </div>

          <div className="info-group">
            <div className="info-label">preferred_username (Login)</div>
            <div className="info-value"><strong>{(payload.preferred_username as string) || 'N/A'}</strong></div>
          </div>

          <div className="info-group">
            <div className="info-label">email / email_verified</div>
            <div className="info-value">
              {(payload.email as string) || 'N/A'} {payload.email_verified ? '✅' : ''}
            </div>
          </div>

          <div className="info-group">
            <div className="info-label">realm_access.roles (RBAC)</div>
            <div className="info-value" style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
              {customRoles.length > 0 ? (
                customRoles.map((r) => (
                  <span key={r} className="badge badge-authenticated" style={{ fontSize: '0.8rem' }}>
                    {r}
                  </span>
                ))
              ) : (
                <span style={{ color: 'var(--text-muted)' }}>Nenhuma role customizada</span>
              )}
            </div>
          </div>

          <div className="info-group">
            <div className="info-label">iss (Issuer / Emissor)</div>
            <div className="info-value"><code>{(payload.iss as string) || 'N/A'}</code></div>
          </div>

          <div className="info-group">
            <div className="info-label">azp (Authorized Party / Client)</div>
            <div className="info-value"><code>{(payload.azp as string) || 'N/A'}</code></div>
          </div>

          <div className="info-group">
            <div className="info-label">exp (Data/Hora de Expiração)</div>
            <div className="info-value" style={{ color: 'var(--accent-green)' }}>
              {formatTimestamp(payload.exp)}
            </div>
          </div>

          <div className="info-group">
            <div className="info-label">iat (Data/Hora de Emissão)</div>
            <div className="info-value">
              {formatTimestamp(payload.iat)}
            </div>
          </div>
        </div>
      ) : (
        <div>
          <div className="info-group">
            <div className="info-label">Token Bruto (String Criptografada)</div>
            <pre style={{ fontSize: '0.75rem', color: 'var(--accent-green)', wordBreak: 'break-all', whiteSpace: 'pre-wrap', maxHeight: '100px', overflowY: 'auto' }}>
              {activeTab === 'access' ? tokens.access_token : activeTab === 'id' ? tokens.id_token : tokens.refresh_token}
            </pre>
          </div>

          <div className="info-group" style={{ marginTop: '1rem' }}>
            <div className="info-label">Payload JSON Completo Decodificado</div>
            <pre style={{ color: 'var(--text-primary)', maxHeight: '250px', overflowY: 'auto' }}>
              {JSON.stringify(payload, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
