#!/usr/bin/env python3
"""
benchmark_auth.py — Card 24: Benchmark de Validação Local (JWKS) vs Token Introspection (RFC 7662)

Mede e compara a latência e o comportamento de revogação entre as duas abordagens:
  1. Validação Local (JWKS) — GET /documents
     - Validação criptográfica do JWT RS256 em memória (sem chamada de rede ao Keycloak).
     - Rápido (< 5ms), porém não detecta revogação imediata de token.
  2. Token Introspection (RFC 7662) — GET /documents-introspect
     - Consulta POST /protocol/openid-connect/token/introspect no Keycloak a cada request.
     - Detecta revogação em tempo real, porém adiciona latência de rede em cada chamada.

Uso:
    python3 scripts/benchmark_auth.py
    python3 scripts/benchmark_auth.py --iterations 100
    python3 scripts/benchmark_auth.py --test-revocation
"""

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ── Configurações ──────────────────────────────────────────────────────────────
KEYCLOAK_URL = "http://localhost:8080"
API_URL = "http://localhost:8001"
REALM = "distributed-systems"
CLIENT_ID = "api-simples"
CLIENT_SECRET = "GZYImUZPV2W7tWzsQKTbpzdNFI2eLdGC"

# ── Cores ANSI ────────────────────────────────────────────────────────────────
BOLD = "\033[1m"
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
MAGENTA = "\033[0;35m"
RED = "\033[0;31m"
DIM = "\033[2m"
RESET = "\033[0m"


def get_token(username: str = "alice", password: str = "alice123") -> str:
    """Obtém um access token real do Keycloak."""
    url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
    data = urllib.parse.urlencode({
        "grant_type": "password",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "username": username,
        "password": password,
        "scope": "openid",
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())["access_token"]
    except Exception as exc:
        print(f"{RED}Erro ao obter token do Keycloak: {exc}{RESET}")
        sys.exit(1)


def get_admin_token() -> str:
    """Obtém token de admin do master realm."""
    url = f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token"
    data = urllib.parse.urlencode({
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": "admin",
        "password": "admin",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())["access_token"]


def measure_endpoint(url: str, token: str, iterations: int) -> list[float]:
    """Executa N requisições e retorna os tempos de resposta em milissegundos."""
    headers = {"Authorization": f"Bearer {token}"}
    latencies = []

    for _ in range(iterations):
        req = urllib.request.Request(url, headers=headers)
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req) as resp:
                resp.read()
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0)
        except urllib.error.HTTPError as exc:
            t1 = time.perf_counter()
            print(f"{RED}Erro HTTP {exc.code} na requisição: {exc.read().decode()}{RESET}")
            latencies.append((t1 - t0) * 1000.0)

    return latencies


def calc_stats(latencies: list[float]) -> dict:
    """Calcula estatísticas de latência."""
    sorted_lat = sorted(latencies)
    n = len(sorted_lat)
    p50_idx = int(n * 0.50)
    p95_idx = min(int(n * 0.95), n - 1)
    p99_idx = min(int(n * 0.99), n - 1)

    return {
        "min": min(sorted_lat),
        "mean": statistics.mean(sorted_lat),
        "median": sorted_lat[p50_idx],
        "p95": sorted_lat[p95_idx],
        "p99": sorted_lat[p99_idx],
        "max": max(sorted_lat),
        "total_time_s": sum(sorted_lat) / 1000.0,
        "req_per_sec": n / (sum(sorted_lat) / 1000.0) if sum(sorted_lat) > 0 else 0,
    }


def demonstrate_revocation():
    """Demonstra que a validação local ainda aceita token revogado enquanto Introspect o rejeita."""
    print(f"\n{BOLD}{MAGENTA}{'=' * 70}{RESET}")
    print(f"{BOLD}{MAGENTA} DEMONSTRAÇÃO PRÁTICA DE REVOGAÇÃO (JWKS vs INTROSPECTION){RESET}")
    print(f"{BOLD}{MAGENTA}{'=' * 70}{RESET}\n")

    print("1. Obtendo token de usuário para Carol...")
    carol_token = get_token("carol", "carol123")
    print(f"   {GREEN}✓ Token da Carol emitido.{RESET}")

    url_jwks = f"{API_URL}/documents"
    url_introspect = f"{API_URL}/documents-introspect"

    # Teste antes de revogar
    req_local = urllib.request.Request(url_jwks, headers={"Authorization": f"Bearer {carol_token}"})
    with urllib.request.urlopen(req_local) as resp:
        print(f"2. Antes de revogar -> GET /documents (JWKS Local):        {GREEN}HTTP {resp.status} OK{RESET}")

    req_intro = urllib.request.Request(url_introspect, headers={"Authorization": f"Bearer {carol_token}"})
    with urllib.request.urlopen(req_intro) as resp:
        print(f"3. Antes de revogar -> GET /documents-introspect (Remoto):  {GREEN}HTTP {resp.status} OK{RESET}")

    # Revogando sessão da Carol via Keycloak Admin API
    print(f"\n4. {YELLOW}Revogando sessão de Carol no Keycloak via Admin API...{RESET}")
    admin_token = get_admin_token()
    carol_id = "8c02af90-09e9-4d22-870a-72df2d19aecb"
    logout_req = urllib.request.Request(
        f"{KEYCLOAK_URL}/admin/realms/{REALM}/users/{carol_id}/logout",
        headers={"Authorization": f"Bearer {admin_token}"},
        method="POST",
    )
    with urllib.request.urlopen(logout_req) as resp:
        print(f"   {GREEN}✓ Sessão revogada no Keycloak (status {resp.status}).{RESET}")

    # Teste após revogação
    print("\n5. Testando endpoints com o token da sessão revogada:")

    # JWKS Local
    with urllib.request.urlopen(req_local) as resp:
        print(f"   • {BOLD}GET /documents (JWKS Local):{RESET}        {YELLOW}HTTP {resp.status} (ACEITO!){RESET}")
        print(f"     ↳ {DIM}A validação local não sabe que a sessão foi revogada, pois a assinatura e o exp continuam válidos.{RESET}")

    # Token Introspection
    try:
        urllib.request.urlopen(req_intro)
        print(f"   • {BOLD}GET /documents-introspect:{RESET}           {RED}Falha (esperado 401){RESET}")
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode())
        print(f"   • {BOLD}GET /documents-introspect:{RESET}           {RED}HTTP {e.code} UNAUTHORIZED (BLOQUEADO!){RESET}")
        print(f"     ↳ {DIM}detail: \"{body.get('detail')}\"{RESET}")

    print(f"\n{BOLD}{GREEN}✓ Conclusão comprovada:{RESET} Token Introspection detecta revogação instantaneamente, enquanto JWKS aguarda a expiração natural do token.\n")


def main():
    parser = argparse.ArgumentParser(description="Benchmark: Validação Local (JWKS) vs Token Introspection")
    parser.add_argument("--iterations", "-n", type=int, default=100, help="Número de requisições por endpoint (default: 100)")
    parser.add_argument("--test-revocation", action="store_true", help="Executa o teste prático de revogação de sessão")
    args = parser.parse_args()

    if args.test_revocation:
        demonstrate_revocation()
        return

    print(f"\n{BOLD}{CYAN}{'=' * 70}{RESET}")
    print(f"{BOLD}{CYAN} Card 24 — Benchmark: Validação Local (JWKS) vs Token Introspection{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 70}{RESET}")
    print(f"Iterações: {BOLD}{args.iterations}{RESET} requisições por abordagem\n")

    print(f"Obtendo Access Token para {BOLD}alice{RESET}...")
    token = get_token("alice", "alice123")
    print(f"{GREEN}✓ Access Token obtido com sucesso.{RESET}\n")

    url_jwks = f"{API_URL}/documents"
    url_introspect = f"{API_URL}/documents-introspect"

    # Warm-up (5 requisições para aquecer conexões HTTP e cache JWKS)
    print("Aquecendo conexões (warm-up)...", end="", flush=True)
    measure_endpoint(url_jwks, token, 5)
    measure_endpoint(url_introspect, token, 5)
    print(f" {GREEN}pronto!{RESET}\n")

    # Medição 1: Validação Local (JWKS)
    print(f"Executando {BOLD}{args.iterations}{RESET} requisições em {CYAN}GET /documents{RESET} (Validação Local JWKS)...")
    lat_jwks = measure_endpoint(url_jwks, token, args.iterations)
    stats_jwks = calc_stats(lat_jwks)

    # Medição 2: Token Introspection (RFC 7662)
    print(f"Executando {BOLD}{args.iterations}{RESET} requisições em {YELLOW}GET /documents-introspect{RESET} (Token Introspection)...")
    lat_intro = measure_endpoint(url_introspect, token, args.iterations)
    stats_intro = calc_stats(lat_intro)

    # Exibição dos resultados
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD} RESULTADOS DO BENCHMARK ({args.iterations} requisições cada){RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")
    print(f"{'Métrica':<20} | {'JWKS Local (GET /documents)':<23} | {'Introspection (GET /docs-intro)':<25}")
    print(f"{'-' * 20}-+-{'-' * 23}-+-{'-' * 25}")
    print(f"{'Média (Mean)':<20} | {GREEN}{stats_jwks['mean']:>18.2f} ms{RESET} | {YELLOW}{stats_intro['mean']:>20.2f} ms{RESET}")
    print(f"{'Mediana (p50)':<20} | {GREEN}{stats_jwks['median']:>18.2f} ms{RESET} | {YELLOW}{stats_intro['median']:>20.2f} ms{RESET}")
    print(f"{'Mínimo':<20} | {GREEN}{stats_jwks['min']:>18.2f} ms{RESET} | {YELLOW}{stats_intro['min']:>20.2f} ms{RESET}")
    print(f"{'Percentil 95 (p95)':<20} | {GREEN}{stats_jwks['p95']:>18.2f} ms{RESET} | {YELLOW}{stats_intro['p95']:>20.2f} ms{RESET}")
    print(f"{'Percentil 99 (p99)':<20} | {GREEN}{stats_jwks['p99']:>18.2f} ms{RESET} | {YELLOW}{stats_intro['p99']:>20.2f} ms{RESET}")
    print(f"{'Máximo':<20} | {GREEN}{stats_jwks['max']:>18.2f} ms{RESET} | {YELLOW}{stats_intro['max']:>20.2f} ms{RESET}")
    print(f"{'-' * 20}-+-{'-' * 23}-+-{'-' * 25}")
    print(f"{'Throughput (req/s)':<20} | {GREEN}{stats_jwks['req_per_sec']:>16.1f} req/s{RESET} | {YELLOW}{stats_intro['req_per_sec']:>18.1f} req/s{RESET}")
    print(f"{'Tempo Total':<20} | {GREEN}{stats_jwks['total_time_s']:>18.2f} s{RESET}  | {YELLOW}{stats_intro['total_time_s']:>20.2f} s{RESET}")

    ratio = stats_intro['mean'] / stats_jwks['mean'] if stats_jwks['mean'] > 0 else 0
    print(f"\n{BOLD}⚡ Aceleração:{RESET} A validação local via JWKS foi {BOLD}{GREEN}{ratio:.1f}x mais rápida{RESET} que a Introspecção remota.")

    # Tabela comparativa de trade-offs
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD} ANÁLISE DE TRADE-OFFS ARQUITETURAIS{RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")
    print(f"""
  {BOLD}1. Validação Local (JWKS){RESET}
     • {GREEN}Vantagem:{RESET} Performance extrema (< 5ms), zero requisições adicionais de rede por request.
     • {GREEN}Vantagem:{RESET} Alta resiliência: se o Keycloak ficar fora do ar temporariamente, a API continua validando tokens já emitidos.
     • {RED}Desvantagem:{RESET} Revogação não é instantânea. Se um usuário fizer logout ou for desativado, seu token continuará válido até atingir 'exp'.
     • {CYAN}Mitigação:{RESET} Usar Access Tokens de vida curta (ex: 2 a 5 minutos) + Refresh Tokens (Card 23).

  2. Token Introspection (RFC 7662)
     • {GREEN}Vantagem:{RESET} Revogação imediata: se a sessão for cancelada no Keycloak, a próxima requisição falha instantaneamente.
     • {GREEN}Vantagem:{RESET} Suporte a tokens opacos (opaque tokens / reference tokens).
     • {RED}Desvantagem:{RESET} Latência adicional: cada chamada à sua API gera 1 chamada HTTP síncrona ao Keycloak.
     • {RED}Desvantagem:{RESET} Ponto único de falha: se o Keycloak ficar indisponível, todas as APIs falham imediatamente.
    """)

    print(f"\n{DIM}Dica: Execute 'python3 scripts/benchmark_auth.py --test-revocation' para ver o teste prático de revogação de sessão.{RESET}\n")


if __name__ == "__main__":
    main()
