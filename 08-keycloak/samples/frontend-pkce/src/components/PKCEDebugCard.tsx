import React, { useEffect, useState } from 'react';
import { createPKCEParams, PKCEPair } from '../auth/pkce';

export const PKCEDebugCard: React.FC = () => {
  const [pkceData, setPkceData] = useState<PKCEPair | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const generateNewPair = async () => {
    setLoading(true);
    const data = await createPKCEParams();
    setPkceData(data);
    setLoading(false);
  };

  useEffect(() => {
    generateNewPair();
  }, []);

  if (loading || !pkceData) {
    return (
      <div className="card">
        <h3 className="card-title">⚙️ PKCE Debug & Gerador</h3>
        <p>Gerando par de chaves PKCE (code_verifier + code_challenge)...</p>
      </div>
    );
  }

  const handleStartLogin = () => {
    sessionStorage.setItem('pkce_code_verifier', pkceData.codeVerifier);
    sessionStorage.setItem('pkce_state', pkceData.state);
    window.location.href = pkceData.authorizationUrl;
  };

  return (
    <div className="card" style={{ gridColumn: '1 / -1' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid var(--border-color)',
          paddingBottom: '0.5rem',
          marginBottom: '1rem',
        }}
      >
        <h3 className="card-title" style={{ borderBottom: 'none', marginBottom: 0 }}>
          🛠️ Card 11: Inspeção Didática do Par PKCE (Gerado em Memória)
        </h3>
        <button className="btn btn-primary" onClick={generateNewPair}>
          🔄 Gerar Novo Par PKCE
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <div className="info-group">
          <div className="info-label">1. code_verifier (Segredo Aleatório em Memória)</div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            String aleatória de 64 caracteres gerada via <code>window.crypto</code>. Fica guardada na SPA e NUNCA viaja na URL inicial.
          </p>
          <pre style={{ color: 'var(--accent-green)', wordBreak: 'break-all' }}>
            {pkceData.codeVerifier}
          </pre>
        </div>

        <div className="info-group">
          <div className="info-label">2. code_challenge (SHA-256 do Verifier)</div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Calculado com <code>SHA256(code_verifier)</code>. É este valor que é enviado ao Keycloak no parâmetro <code>code_challenge</code>.
          </p>
          <pre style={{ color: 'var(--accent-blue)', wordBreak: 'break-all' }}>
            {pkceData.codeChallenge}
          </pre>
        </div>
      </div>

      <div className="info-group" style={{ marginTop: '1rem' }}>
        <div className="info-label">3. State (Token Anti-CSRF)</div>
        <pre style={{ color: 'var(--text-primary)' }}>{pkceData.state}</pre>
      </div>

      <div className="info-group" style={{ marginTop: '1rem' }}>
        <div className="info-label">4. URL de Autorização Construída (Keycloak Auth Endpoint)</div>
        <pre style={{ fontSize: '0.75rem', color: 'var(--accent-blue)', whiteSpace: 'pre-wrap' }}>
          {pkceData.authorizationUrl}
        </pre>
      </div>

      <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
        <button
          className="btn btn-primary"
          style={{ backgroundColor: 'var(--accent-green)', fontSize: '1.05rem', padding: '0.75rem 1.5rem' }}
          onClick={handleStartLogin}
        >
          🚀 Testar Redirecionamento de Login no Keycloak
        </button>
        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          Ao clicar, o navegador abre a tela de login do Keycloak com os parâmetros PKCE acima.
        </span>
      </div>
    </div>
  );
};
