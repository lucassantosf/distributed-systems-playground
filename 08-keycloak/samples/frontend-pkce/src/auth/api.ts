/**
 * api.ts — Card 16: Interceptor de Requisições com Auto-Refresh Token
 *
 * Envolve a API nativa fetch(). Se o servidor retornar 401 Unauthorized:
 *   1. Tenta renovar os tokens automaticamente via Refresh Token.
 *   2. Se o refresh for bem-sucedido, repete a requisição original com o novo Access Token.
 *   3. Se o refresh falhar, propaga o erro de autenticação para deslogar o usuário.
 */

import { TokenResponse, refreshAccessToken } from './tokens';

export interface RefreshLog {
  timestamp: string;
  reason: string;
  newAccessTokenSnippet: string;
}

export async function fetchWithAuth(
  url: string,
  options: RequestInit = {},
  tokens: TokenResponse | null,
  onTokensRefreshed: (newTokens: TokenResponse, log: RefreshLog) => void
): Promise<Response> {
  // Se não temos tokens, faz a chamada original (que retornará 401)
  if (!tokens?.access_token) {
    return fetch(url, options);
  }

  // Prepara os headers incluindo o Bearer Token
  const headers = new Headers(options.headers || {});
  headers.set('Authorization', `Bearer ${tokens.access_token}`);

  // Primeira tentativa
  let response = await fetch(url, { ...options, headers });

  // Se retornou 401 e temos um Refresh Token, tenta a renovação automática (Card 16)
  if (response.status === 401 && tokens.refresh_token) {
    console.warn('⚠️ HTTP 401 recebido! Executando refresh token automático...');

    try {
      const newTokens = await refreshAccessToken(tokens.refresh_token);

      const log: RefreshLog = {
        timestamp: new Date().toLocaleTimeString(),
        reason: 'HTTP 401 (Access Token Expirado/Inválido)',
        newAccessTokenSnippet: `${newTokens.access_token.substring(0, 30)}...`,
      };

      // Notifica o React State para atualizar os tokens mantidos em memória
      onTokensRefreshed(newTokens, log);

      // Repete a requisição original com o NOVO Access Token
      headers.set('Authorization', `Bearer ${newTokens.access_token}`);
      response = await fetch(url, { ...options, headers });
    } catch (refreshErr) {
      console.error('❌ Falha no Refresh Token automático:', refreshErr);
      // Propaga a resposta 401 original se a renovação falhar
    }
  }

  return response;
}
