import { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { AuthStateCard } from './components/AuthStateCard';
import { DocumentsCard } from './components/DocumentsCard';
import { PKCEDebugCard } from './components/PKCEDebugCard';
import { CallbackDebugCard } from './components/CallbackDebugCard';
import { createPKCEParams } from './auth/pkce';
import { checkAuthorizationCallback, clearUrlParams, CallbackResult } from './auth/callback';
import './index.css';

export function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [username, setUsername] = useState<string | undefined>(undefined);
  const [callbackData, setCallbackData] = useState<CallbackResult | null>(null);

  useEffect(() => {
    // Executado ao carregar a página: checa se fomos redirecionados do Keycloak com code/state
    const result = checkAuthorizationCallback();
    if (result) {
      setCallbackData(result);
      clearUrlParams();
    }
  }, []);

  const handleLogin = async () => {
    // Gera par PKCE dinamicamente e redireciona para o Keycloak
    const pkceData = await createPKCEParams();
    sessionStorage.setItem('pkce_code_verifier', pkceData.codeVerifier);
    sessionStorage.setItem('pkce_state', pkceData.state);
    window.location.href = pkceData.authorizationUrl;
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setUsername(undefined);
    setCallbackData(null);
    sessionStorage.removeItem('pkce_code_verifier');
    sessionStorage.removeItem('pkce_state');
  };

  return (
    <div className="container">
      <Header
        isAuthenticated={isAuthenticated}
        username={username}
        onLogin={handleLogin}
        onLogout={handleLogout}
      />

      <main className="grid">
        <AuthStateCard
          isAuthenticated={isAuthenticated}
          userClaims={
            isAuthenticated
              ? {
                  sub: '5d0cca8a-69f3-45de-9620-19ae469f06e9',
                  preferred_username: 'alice',
                  email: 'alice@example.com',
                  realm_access: { roles: ['admin'] },
                }
              : null
          }
        />
        <DocumentsCard isAuthenticated={isAuthenticated} />

        {callbackData && <CallbackDebugCard callbackData={callbackData} />}

        <PKCEDebugCard />
      </main>
    </div>
  );
}

export default App;
