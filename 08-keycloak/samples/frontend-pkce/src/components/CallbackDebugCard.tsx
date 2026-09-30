import React from 'react';
import { CallbackResult } from '../auth/callback';

interface CallbackDebugCardProps {
  callbackData: CallbackResult;
}

export const CallbackDebugCard: React.FC<CallbackDebugCardProps> = ({
  callbackData,
}) => {
  return (
    <div className="card" style={{ gridColumn: '1 / -1', borderColor: callbackData.stateValid ? 'var(--accent-green)' : 'var(--accent-red)' }}>
      <h3 className="card-title" style={{ color: callbackData.stateValid ? 'var(--accent-green)' : 'var(--accent-red)' }}>
        📥 Card 12: Authorization Code Capturado do Keycloak
      </h3>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <div className="info-group">
          <div className="info-label">1. Authorization Code (Temporário na URL)</div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Código temporário de uso único emitido pelo Keycloak na URL. Será trocado pelos tokens no Card 13.
          </p>
          <pre style={{ color: 'var(--accent-blue)', wordBreak: 'break-all' }}>
            {callbackData.code}
          </pre>
        </div>

        <div className="info-group">
          <div className="info-label">2. Validação Anti-CSRF (State)</div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Compara o <code>state</code> retornado com o <code>sessionStorage</code>.
          </p>
          <div style={{ marginTop: '0.5rem' }}>
            {callbackData.stateValid ? (
              <span className="badge badge-authenticated" style={{ fontSize: '1rem' }}>
                ✅ State VÁLIDO! (Protegido contra CSRF)
              </span>
            ) : (
              <span className="badge badge-unauthenticated" style={{ fontSize: '1rem' }}>
                ❌ ERRO: State INVÁLIDO! ({callbackData.error})
              </span>
            )}
          </div>
          <pre style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}>
            State Retornado: {callbackData.state}
          </pre>
        </div>
      </div>

      <div className="info-group" style={{ marginTop: '1rem' }}>
        <div className="info-label">3. code_verifier Recuperado da Memória</div>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Este é o segredo PKCE mantido no navegador para provar a identidade na troca pelo token (Card 13).
        </p>
        <pre style={{ color: 'var(--accent-green)', wordBreak: 'break-all' }}>
          {callbackData.codeVerifier || '(nenhum verifier encontrado em sessionStorage)'}
        </pre>
      </div>
    </div>
  );
};
