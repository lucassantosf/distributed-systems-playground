/**
 * pkce.ts — Card 11: Implementação manual de PKCE (Proof Key for Code Exchange)
 *
 * Utiliza a API nativa do navegador (Web Crypto API) para:
 *   1. Gerar o code_verifier (string aleatória de alta entropia)
 *   2. Calcular o code_challenge (SHA-256 do verifier codificado em Base64URL)
 *   3. Gerar o state (token aleatório anti-CSRF)
 *   4. Construir a URL de autorização do Keycloak
 */

export interface PKCEPair {
  codeVerifier: string;
  codeChallenge: string;
  state: string;
  authorizationUrl: string;
  redirectUri: string;
  clientId: string;
  realmUrl: string;
}

// Configurações do Keycloak
export const AUTH_CONFIG = {
  keycloakUrl: 'http://localhost:8080',
  realm: 'distributed-systems',
  clientId: 'frontend-pkce',
  redirectUri: window.location.origin, // http://localhost:5173
  scope: 'openid profile email documents:read',
};

/**
 * Converte um ArrayBuffer para uma string em formato Base64URL (RFC 7515).
 * Base64URL substitui '+' por '-', '/' por '_' e remove os paddings '='.
 */
function bufferToBase64Url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  const base64 = btoa(binary);
  return base64
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

/**
 * Passo 1: Gerar o code_verifier
 * Gera uma string aleatória criptograficamente segura entre 43 e 128 caracteres.
 */
export function generateCodeVerifier(): string {
  const array = new Uint8Array(48); // 48 bytes -> ~64 chars em base64url
  window.crypto.getRandomValues(array);
  return bufferToBase64Url(array.buffer);
}

/**
 * Passo 2: Calcular o code_challenge (S256)
 * Aplica o algoritmo SHA-256 no code_verifier e converte o hash para Base64URL.
 */
export async function generateCodeChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const digest = await window.crypto.subtle.digest('SHA-256', data);
  return bufferToBase64Url(digest);
}

/**
 * Gerador de token anti-CSRF (state)
 */
export function generateState(): string {
  const array = new Uint8Array(16);
  window.crypto.getRandomValues(array);
  return bufferToBase64Url(array.buffer);
}

/**
 * Passo 3: Construir a URL de Autorização do Keycloak
 * Junta todos os parâmetros requeridos pelo OAuth 2.0 + PKCE.
 */
export async function createPKCEParams(): Promise<PKCEPair> {
  const codeVerifier = generateCodeVerifier();
  const codeChallenge = await generateCodeChallenge(codeVerifier);
  const state = generateState();

  const realmUrl = `${AUTH_CONFIG.keycloakUrl}/realms/${AUTH_CONFIG.realm}`;
  const authEndpoint = `${realmUrl}/protocol/openid-connect/auth`;

  const params = new URLSearchParams({
    response_type: 'code',
    client_id: AUTH_CONFIG.clientId,
    redirect_uri: AUTH_CONFIG.redirectUri,
    scope: AUTH_CONFIG.scope,
    state: state,
    code_challenge: codeChallenge,
    code_challenge_method: 'S256',
  });

  const authorizationUrl = `${authEndpoint}?${params.toString()}`;

  return {
    codeVerifier,
    codeChallenge,
    state,
    authorizationUrl,
    redirectUri: AUTH_CONFIG.redirectUri,
    clientId: AUTH_CONFIG.clientId,
    realmUrl,
  };
}
