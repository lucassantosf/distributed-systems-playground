import { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { AuthStateCard } from './components/AuthStateCard';
import { DocumentsCard } from './components/DocumentsCard';
import { PKCEDebugCard } from './components/PKCEDebugCard';
import { CallbackDebugCard } from './components/CallbackDebugCard';
import { TokenViewer } from './components/TokenViewer';
import { RefreshLogCard } from './components/RefreshLogCard';
import { createPKCEParams } from './auth/pkce';
import { checkAuthorizationCallback, clearUrlParams, CallbackResult } from './auth/callback';
import { exchangeCodeForTokens, refreshAccessToken, logoutUser, TokenResponse, decodeJWT } from './auth/tokens';
import { RefreshLog } from './auth/api';
import './index.css';

export function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [username, setUsername] = useState<string | undefined>(undefined);
  const [callbackData, setCallbackData] = useState<CallbackResult | null>(null);
  const [tokens, setTokens] = useState<TokenResponse | null>(null);
  const [userClaims, setUserClaims] = useState<Record<string, unknown> | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [refreshLogs, setRefreshLogs] = useState<RefreshLog[]>([]);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  useEffect(() => {
    const handleCallback = async () => {
      const result = checkAuthorizationCallback();
      if (result) {
        setCallbackData(result);
        clearUrlParams();

        if (result.stateValid && result.code && result.codeVerifier) {
          try {
            const tokenResp = await exchangeCodeForTokens(result.code, result.codeVerifier);
            setTokens(tokenResp);
            setIsAuthenticated(true);

            const decoded = decodeJWT(tokenResp.access_token);
            if (decoded) {
              setUserClaims(decoded.payload);
              const name = (decoded.payload.preferred_username as string) || (decoded.payload.sub as string);
              setUsername(name);
            }
          } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : String(err);
            console.error('Erro na troca de tokens:', err);
            setErrorMsg(`Falha na troca de tokens: ${msg}`);
          }
        }
      }
    };

    handleCallback();
  }, []);

  const handleTokensRefreshed = (newTokens: TokenResponse, log: RefreshLog) => {
    setTokens(newTokens);
    setRefreshLogs((prev) => [log, ...prev]);

    const decoded = decodeJWT(newTokens.access_token);
    if (decoded) {
      setUserClaims(decoded.payload);
      const name = (decoded.payload.preferred_username as string) || (decoded.payload.sub as string);
      setUsername(name);
    }
  };

  const handleManualRefresh = async () => {
    if (!tokens?.refresh_token) {
      alert('Nenhum refresh token disponível!');
      return;
    }

    setRefreshing(true);
    try {
      const newTokens = await refreshAccessToken(tokens.refresh_token);
      const log: RefreshLog = {
        timestamp: new Date().toLocaleTimeString(),
        reason: 'Solicitação Manual pelo Usuário (Botão)',
        newAccessTokenSnippet: `${newTokens.access_token.substring(0, 30)}...`,
      };
      handleTokensRefreshed(newTokens, log);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(`Erro na renovação do token: ${msg}`);
    } finally {
      setRefreshing(false);
    }
  };

  const handleLogin = async () => {
    const pkceData = await createPKCEParams();
    sessionStorage.setItem('pkce_code_verifier', pkceData.codeVerifier);
    sessionStorage.setItem('pkce_state', pkceData.state);
    window.location.href = pkceData.authorizationUrl;
  };

  /**
   * Card 17: Logout completo.
   * Limpa o estado local e chama o Keycloak para destruir a sessão SSO no servidor e no navegador.
   */
  const handleLogout = async () => {
    sessionStorage.removeItem('pkce_code_verifier');
    sessionStorage.removeItem('pkce_state');

    const currentRefreshToken = tokens?.refresh_token;
    const currentIdToken = tokens?.id_token;

    setIsAuthenticated(false);
    setUsername(undefined);
    setCallbackData(null);
    setTokens(null);
    setUserClaims(null);
    setErrorMsg(null);
    setRefreshLogs([]);

    // Executa o logout no Keycloak (destrói cookies SSO do navegador e invalida refresh_token)
    await logoutUser(currentRefreshToken, currentIdToken);
  };

  const roles: string[] =
    (userClaims?.realm_access as { roles?: string[] })?.roles || [];

  return (
    <div className="container">
      <Header
        isAuthenticated={isAuthenticated}
        username={username}
        onLogin={handleLogin}
        onLogout={handleLogout}
      />

      {errorMsg && (
        <div className="card" style={{ borderColor: 'var(--accent-red)', marginBottom: '1.5rem' }}>
          <h3 className="card-title" style={{ color: 'var(--accent-red)' }}>⚠️ Erro na Autenticação</h3>
          <p>{errorMsg}</p>
        </div>
      )}

      <main className="grid">
        <AuthStateCard
          isAuthenticated={isAuthenticated}
          userClaims={userClaims}
        />
        <DocumentsCard
          isAuthenticated={isAuthenticated}
          tokens={tokens}
          userRoles={roles}
          onTokensRefreshed={handleTokensRefreshed}
        />

        {isAuthenticated && (
          <RefreshLogCard
            logs={refreshLogs}
            onManualRefresh={handleManualRefresh}
            loading={refreshing}
          />
        )}

        {tokens && <TokenViewer tokens={tokens} />}

        {callbackData && <CallbackDebugCard callbackData={callbackData} />}

        <PKCEDebugCard />
      </main>
    </div>
  );
}

export default App;
