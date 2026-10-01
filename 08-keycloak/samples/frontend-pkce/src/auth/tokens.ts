/**
 * tokens.ts — Card 13, 16 & 17: Gerenciamento, Renovação e Invalidação (Logout) de Tokens
 */

import { AUTH_CONFIG } from './pkce';

export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  id_token?: string;
  token_type: string;
  expires_in: number;
  refresh_expires_in?: number;
  scope: string;
}

export interface DecodedJWT {
  header: Record<string, unknown>;
  payload: Record<string, unknown>;
}

/**
 * Decodifica um JWT no navegador sem bibliotecas externas.
 */
export function decodeJWT(token: string): DecodedJWT | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;

    const decodeBase64Url = (str: string) => {
      let base64 = str.replace(/-/g, '+').replace(/_/g, '/');
      while (base64.length % 4) {
        base64 += '=';
      }
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonPayload);
    };

    return {
      header: decodeBase64Url(parts[0]),
      payload: decodeBase64Url(parts[1]),
    };
  } catch (err) {
    console.error('Erro ao decodificar JWT:', err);
    return null;
  }
}

/**
 * Card 13: Troca o Authorization Code pelo conjunto de Tokens.
 */
export async function exchangeCodeForTokens(
  code: string,
  codeVerifier: string
): Promise<TokenResponse> {
  const tokenEndpoint = `${AUTH_CONFIG.keycloakUrl}/realms/${AUTH_CONFIG.realm}/protocol/openid-connect/token`;

  const bodyParams = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: AUTH_CONFIG.clientId,
    redirect_uri: AUTH_CONFIG.redirectUri,
    code: code,
    code_verifier: codeVerifier,
  });

  const response = await fetch(tokenEndpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: bodyParams.toString(),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.error_description ||
        errorData.error ||
        `Falha na troca de tokens (HTTP ${response.status})`
    );
  }

  return response.json();
}

/**
 * Card 16: Renova o Access Token usando o Refresh Token.
 */
export async function refreshAccessToken(refreshToken: string): Promise<TokenResponse> {
  const tokenEndpoint = `${AUTH_CONFIG.keycloakUrl}/realms/${AUTH_CONFIG.realm}/protocol/openid-connect/token`;

  const bodyParams = new URLSearchParams({
    grant_type: 'refresh_token',
    client_id: AUTH_CONFIG.clientId,
    refresh_token: refreshToken,
  });

  const response = await fetch(tokenEndpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: bodyParams.toString(),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.error_description ||
        errorData.error ||
        `Falha na renovação via Refresh Token (HTTP ${response.status})`
    );
  }

  return response.json();
}

/**
 * Card 17: Logout completo no Keycloak (destrói a sessão SSO no servidor e limpa os cookies do browser).
 */
export async function logoutUser(refreshToken?: string, idToken?: string): Promise<void> {
  // 1. Invalida o refresh_token no servidor via POST
  if (refreshToken) {
    try {
      const logoutEndpoint = `${AUTH_CONFIG.keycloakUrl}/realms/${AUTH_CONFIG.realm}/protocol/openid-connect/logout`;
      await fetch(logoutEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          client_id: AUTH_CONFIG.clientId,
          refresh_token: refreshToken,
        }).toString(),
      });
    } catch (err) {
      console.warn('Erro ao invalidar refresh_token no servidor:', err);
    }
  }

  // 2. Redireciona o navegador para o endpoint de logout do Keycloak para destruir os cookies de SSO do browser
  const redirectUri = encodeURIComponent(AUTH_CONFIG.redirectUri);
  let browserLogoutUrl = `${AUTH_CONFIG.keycloakUrl}/realms/${AUTH_CONFIG.realm}/protocol/openid-connect/logout?client_id=${AUTH_CONFIG.clientId}&post_logout_redirect_uri=${redirectUri}`;
  if (idToken) {
    browserLogoutUrl += `&id_token_hint=${encodeURIComponent(idToken)}`;
  }

  // Redireciona o navegador para o Keycloak limpar os cookies SSO e voltar limpo
  window.location.href = browserLogoutUrl;
}
