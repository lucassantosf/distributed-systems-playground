#!/usr/bin/env python3
"""
decode_tokens.py — Card 4: Anatomia do JWT

Obtém tokens reais do Keycloak para alice, bob e carol e decodifica
os claims de cada token (Access Token, ID Token, Refresh Token),
explicando o papel de cada campo.

Uso:
    python3 scripts/decode_tokens.py
    python3 scripts/decode_tokens.py --user alice
    python3 scripts/decode_tokens.py --user alice --token-type access
"""

import base64
import json
import sys
import argparse
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import HTTPError

# ── Configuração ──────────────────────────────────────────────────────────────

KEYCLOAK_URL   = "http://localhost:8080"
REALM          = "distributed-systems"
CLIENT_ID      = "api-simples"
CLIENT_SECRET  = "GZYImUZPV2W7tWzsQKTbpzdNFI2eLdGC"

USERS = [
    {"username": "alice", "password": "alice123"},
    {"username": "bob",   "password": "bob123"},
    {"username": "carol", "password": "carol123"},
]

TOKEN_URL = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"

# ── Cores ANSI ────────────────────────────────────────────────────────────────

BOLD    = "\033[1m"
CYAN    = "\033[0;36m"
GREEN   = "\033[0;32m"
YELLOW  = "\033[0;33m"
MAGENTA = "\033[0;35m"
RED     = "\033[0;31m"
DIM     = "\033[2m"
RESET   = "\033[0m"

# ── Explicações dos claims ─────────────────────────────────────────────────────

CLAIM_EXPLANATIONS = {
    "sub":                    "Identificador único do usuário (Subject) — UUID estável, nunca muda",
    "iss":                    "Issuer — quem emitiu o token (URL do Keycloak + realm)",
    "aud":                    "Audience — para quem o token é destinado (client ou lista de clients)",
    "azp":                    "Authorized Party — client que solicitou o token",
    "exp":                    "Expiration — quando o token expira (Unix timestamp)",
    "iat":                    "Issued At — quando o token foi emitido (Unix timestamp)",
    "jti":                    "JWT ID — identificador único desta emissão (permite detectar replay)",
    "typ":                    "Type — tipo do token: Bearer, Refresh, ID",
    "preferred_username":     "Nome de login do usuário",
    "email":                  "E-mail do usuário",
    "given_name":             "Primeiro nome",
    "family_name":            "Sobrenome",
    "name":                   "Nome completo",
    "email_verified":         "Se o e-mail foi verificado",
    "realm_access":           "Roles do usuário no realm (o que você usa para RBAC)",
    "resource_access":        "Roles específicas por client (RBAC no nível de client)",
    "scope":                  "Escopos autorizados — o que o token 'promete' poder acessar",
    "session_state":          "ID da sessão no Keycloak (usado para logout centralizado)",
    "acr":                    "Authentication Context Class Reference — nível de autenticação usado",
    "sid":                    "Session ID (duplicado de session_state em versões mais recentes)",
    "nonce":                  "Valor aleatório incluído pelo client para prevenir replay (PKCE flow)",
    "at_hash":                "Hash do Access Token — liga o ID Token ao Access Token emitido junto",
    "auth_time":              "Quando o usuário se autenticou pela última vez",
    "typ":                    "Tipo do JWT: 'Bearer' (access), 'Refresh' ou 'ID'",
}

# ── Funções ───────────────────────────────────────────────────────────────────

def get_tokens(username: str, password: str) -> dict:
    """Obtém access_token, refresh_token e id_token via Resource Owner Password Credentials."""
    data = urlencode({
        "grant_type":    "password",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "username":      username,
        "password":      password,
        "scope":         "openid profile email",
    }).encode()

    req = Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urlopen(req) as resp:
            return json.load(resp)
    except HTTPError as e:
        body = json.load(e)
        print(f"{RED}Erro ao obter token para {username}: {body}{RESET}")
        sys.exit(1)


def decode_jwt(token: str) -> dict:
    """Decodifica o payload do JWT sem verificar assinatura (apenas base64url)."""
    parts = token.split(".")
    if len(parts) != 3:
        return {"_error": "Não é um JWT válido (não tem 3 partes)"}
    payload = parts[1]
    # Adiciona padding se necessário
    payload += "=" * (4 - len(payload) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception as e:
        return {"_error": str(e)}


def format_timestamp(ts: int) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def print_claims(claims: dict, title: str, color: str) -> None:
    print(f"\n  {color}{BOLD}── {title} ──{RESET}")
    for key, value in claims.items():
        explanation = CLAIM_EXPLANATIONS.get(key, "")

        # Formata timestamps
        if key in ("exp", "iat", "auth_time") and isinstance(value, int):
            value_str = f"{value}  →  {format_timestamp(value)}"
        elif key == "realm_access" and isinstance(value, dict):
            roles = value.get("roles", [])
            value_str = f"{{'roles': {roles}}}"
        else:
            value_str = repr(value)

        print(f"    {CYAN}{key:25s}{RESET} {value_str}")
        if explanation:
            print(f"    {DIM}{'':25s} ↳ {explanation}{RESET}")


def print_token_section(user: str, tokens: dict, token_type: str) -> None:
    access_raw   = tokens.get("access_token", "")
    refresh_raw  = tokens.get("refresh_token", "")
    id_raw       = tokens.get("id_token", "")

    show_all = token_type == "all"

    if show_all or token_type == "access":
        claims = decode_jwt(access_raw)
        ttl = claims.get("exp", 0) - claims.get("iat", 0)
        print_claims(
            claims,
            f"ACCESS TOKEN  (TTL: {ttl}s — autorização, enviado para as APIs)",
            GREEN,
        )
        if show_all:
            print(f"\n    {DIM}Token bruto (primeiros 80 chars):{RESET}")
            print(f"    {DIM}{access_raw[:80]}...{RESET}")

    if show_all or token_type == "id":
        if id_raw:
            claims = decode_jwt(id_raw)
            print_claims(
                claims,
                "ID TOKEN  (identidade, usado APENAS pelo frontend — não enviar para APIs)",
                MAGENTA,
            )
        else:
            print(f"\n  {YELLOW}ID Token não retornado (adicione scope=openid na requisição){RESET}")

    if show_all or token_type == "refresh":
        if refresh_raw:
            claims = decode_jwt(refresh_raw)
            ttl = claims.get("exp", 0) - claims.get("iat", 0)
            print_claims(
                claims,
                f"REFRESH TOKEN  (TTL: {ttl}s — usado para renovar o access token)",
                YELLOW,
            )
        else:
            print(f"\n  {YELLOW}Refresh Token não retornado{RESET}")


def print_comparison(all_tokens: dict) -> None:
    """Compara as roles dos 3 usuários lado a lado."""
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN} COMPARATIVO: realm_access.roles por usuário{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")
    for username, tokens in all_tokens.items():
        claims = decode_jwt(tokens.get("access_token", ""))
        roles = claims.get("realm_access", {}).get("roles", [])
        custom_roles = [r for r in roles if r not in ("default-roles-distributed-systems", "offline_access", "uma_authorization")]
        print(f"  {GREEN}{username:8s}{RESET} → realm_access.roles = {custom_roles}")

    print(f"""
{DIM}  Observação: o campo realm_access.roles é o que os serviços (Sample A, B, C)
  vão ler para decidir o que cada usuário pode acessar — é o coração do RBAC.{RESET}
""")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Decodifica JWTs do Keycloak para fins de aprendizado")
    parser.add_argument("--user",       choices=["alice", "bob", "carol", "all"], default="all",
                        help="Usuário para decodificar (padrão: all)")
    parser.add_argument("--token-type", choices=["access", "id", "refresh", "all"], default="all",
                        dest="token_type", help="Tipo de token para exibir (padrão: all)")
    args = parser.parse_args()

    target_users = USERS if args.user == "all" else [u for u in USERS if u["username"] == args.user]

    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN} Card 4 — Anatomia do JWT{RESET}")
    print(f"{BOLD}{CYAN} Realm: {REALM} | Keycloak: {KEYCLOAK_URL}{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")

    all_tokens = {}

    for user in target_users:
        username = user["username"]
        print(f"\n{BOLD}{'─'*60}{RESET}")
        print(f"{BOLD} Usuário: {GREEN}{username}{RESET}  (senha: {user['password']})")
        print(f"{BOLD}{'─'*60}{RESET}")

        tokens = get_tokens(username, user["password"])
        all_tokens[username] = tokens

        token_types = {k: type(tokens[k]).__name__ for k in tokens if "token" in k}
        print(f"  {DIM}Token types retornados: {token_types}{RESET}")
        print_token_section(username, tokens, args.token_type)

    if args.user == "all" and args.token_type in ("all", "access"):
        print_comparison(all_tokens)

    print(f"{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{DIM}Dica: Cole qualquer token em https://jwt.io para visualização gráfica.")
    print(f"      A assinatura não pode ser verificada sem a chave pública do Keycloak.")
    print(f"      JWKS: {KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/certs{RESET}\n")


if __name__ == "__main__":
    main()
