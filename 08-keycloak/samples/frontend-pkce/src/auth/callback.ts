export interface CallbackResult {
  code: string;
  state: string;
  codeVerifier: string;
  stateValid: boolean;
  error?: string;
  errorDescription?: string;
}

export function checkAuthorizationCallback(): CallbackResult | null {
  const urlParams = new URLSearchParams(window.location.search);

  const code = urlParams.get('code');
  const state = urlParams.get('state');
  const error = urlParams.get('error');
  const errorDescription = urlParams.get('error_description');

  if (error) {
    return {
      code: '',
      state: state || '',
      codeVerifier: '',
      stateValid: false,
      error: error,
      errorDescription: errorDescription || 'Erro no redirecionamento do Keycloak',
    };
  }

  if (!code || !state) {
    return null;
  }

  const savedState = sessionStorage.getItem('pkce_state');
  const savedVerifier = sessionStorage.getItem('pkce_code_verifier') || '';

  const stateValid = savedState !== null && savedState === state;

  return {
    code,
    state,
    codeVerifier: savedVerifier,
    stateValid,
    error: stateValid ? undefined : 'Estado anti-CSRF inválido!',
  };
}

export function clearUrlParams(): void {
  if (window.location.search) {
    const cleanUrl = window.location.origin + window.location.pathname;
    window.history.replaceState({}, document.title, cleanUrl);
  }
}
