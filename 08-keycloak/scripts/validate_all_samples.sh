#!/usr/bin/env bash
# =============================================================================
# validate_all_samples.sh — Card 26: Validação End-to-End de Todos os Samples
#
# Valida automaticamente os três samples do ecossistema Keycloak:
#   - Keycloak Server (:8080) & Realm distributed-systems
#   - Sample A: api-simples (:8001) — JWT Validation, JWKS, RBAC & Scopes
#   - Sample B: frontend-pkce (:5173) — Web Server & OIDC/PKCE Endpoints
#   - Sample C: bff-m2m (:8002 & :8003) — BFF Proxy & M2M Service-to-Service
#
# Uso:
#   bash scripts/validate_all_samples.sh
#
# Pré-requisitos:
#   - docker compose up --build -d
#   - curl, python3 disponíveis no PATH
# =============================================================================

set -euo pipefail

START_TIME=$(date +%s)

# ── Configuração de URLs e Credenciais ────────────────────────────────────────

KEYCLOAK_BASE="http://localhost:8080"
REALM="distributed-systems"
TOKEN_URL="${KEYCLOAK_BASE}/realms/${REALM}/protocol/openid-connect/token"
WELL_KNOWN_URL="${KEYCLOAK_BASE}/realms/${REALM}/.well-known/openid-configuration"

SAMPLE_A_URL="http://localhost:8001"
SAMPLE_B_URL="http://localhost:5173"
SAMPLE_C_BFF_URL="http://localhost:8002"
SAMPLE_C_DOCS_URL="http://localhost:8003"

API_SIMPLES_SECRET="GZYImUZPV2W7tWzsQKTbpzdNFI2eLdGC"
BFF_CLIENT_SECRET="NdZZhMqZmZcsQhsvUequiwpWCLXD2urt"

# ── Cores e Estilos ───────────────────────────────────────────────────────────

GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
CYAN="\033[0;36m"
MAGENTA="\033[0;35m"
BLUE="\033[0;34m"
BOLD="\033[1m"
RESET="\033[0m"

# ── Contadores Globais ────────────────────────────────────────────────────────

PASS=0
FAIL=0

# ── Funções Utilitárias ───────────────────────────────────────────────────────

log_section() {
    local title="$1"
    echo ""
    echo -e "${BOLD}${CYAN}────────────────────────────────────────────────────────────${RESET}"
    echo -e "${BOLD}${CYAN} ${title}${RESET}"
    echo -e "${BOLD}${CYAN}────────────────────────────────────────────────────────────${RESET}"
}

check() {
    local desc="$1"
    local expected="$2"
    local actual="$3"

    if [ "$actual" = "$expected" ]; then
        echo -e "  ${GREEN}✓ PASS${RESET} ${desc} ${YELLOW}(HTTP ${actual})${RESET}"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}✗ FAIL${RESET} ${desc} ${RED}(esperado ${expected}, obtido ${actual})${RESET}"
        FAIL=$((FAIL + 1))
    fi
}

check_condition() {
    local desc="$1"
    local condition="$2"

    if [ "$condition" = "true" ] || [ "$condition" = "1" ]; then
        echo -e "  ${GREEN}✓ PASS${RESET} ${desc}"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}✗ FAIL${RESET} ${desc}"
        FAIL=$((FAIL + 1))
    fi
}

# http_status <método> <url> [token] [body]
http_status() {
    local method="$1"
    local url="$2"
    local token="${3:-}"
    local body="${4:-}"

    local args=(-s -o /dev/null -w "%{http_code}" -X "$method")

    if [ -n "$token" ]; then
        args+=(-H "Authorization: Bearer $token")
    fi

    if [ -n "$body" ]; then
        args+=(-H "Content-Type: application/json" -d "$body")
    fi

    curl "${args[@]}" "$url"
}

# get_user_token <username> <password> [scope]
get_user_token() {
    local username="$1"
    local password="$2"
    local scope="${3:-openid profile email documents:read documents:write}"

    curl -s -X POST "$TOKEN_URL" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "grant_type=password&client_id=api-simples&client_secret=${API_SIMPLES_SECRET}&username=${username}&password=${password}&scope=${scope}" \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token', ''))"
}

# get_service_token <client_id> <client_secret>
get_service_token() {
    local client_id="$1"
    local client_secret="$2"

    curl -s -X POST "$TOKEN_URL" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "grant_type=client_credentials&client_id=${client_id}&client_secret=${client_secret}" \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token', ''))"
}

# decode_token_claim <token> <dotted_field_path>
decode_token_claim() {
    local token="$1"
    local field="$2"

    python3 - "$token" "$field" << 'EOF'
import sys, base64, json

token = sys.argv[1] if len(sys.argv) > 1 else ""
field = sys.argv[2] if len(sys.argv) > 2 else ""

if not token:
    sys.exit(1)

try:
    payload_b64 = token.split('.')[1]
    payload_b64 += '=' * (-len(payload_b64) % 4)
    data = json.loads(base64.urlsafe_b64decode(payload_b64))

    keys = field.split('.')
    val = data
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            val = None
            break

    if isinstance(val, (dict, list)):
        print(json.dumps(val))
    elif val is not None:
        print(val)
    else:
        print("")
except Exception:
    print("")
EOF
}

# ── Cabeçalho Principal ───────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${MAGENTA}======================================================================${RESET}"
echo -e "${BOLD}${MAGENTA}   VALIDAÇÃO END-TO-END — ECOSSISTEMA DISTRIBUÍDO KEYCLOAK (CARD 26)   ${RESET}"
echo -e "${BOLD}${MAGENTA}======================================================================${RESET}"
echo -e "Data/Hora: $(date)"
echo -e "Keycloak:     ${KEYCLOAK_BASE}/realms/${REALM}"
echo -e "Sample A:     ${SAMPLE_A_URL} (api-simples — JWT/RBAC/Scopes)"
echo -e "Sample B:     ${SAMPLE_B_URL} (frontend-pkce — React/OIDC)"
echo -e "Sample C BFF: ${SAMPLE_C_BFF_URL} (BFF Proxy)"
echo -e "Sample C Svc: ${SAMPLE_C_DOCS_URL} (docs-service — M2M)"

# ── Fase 0: Health Checks dos Serviços ────────────────────────────────────────

log_section "Fase 0: Verificação de Saúde dos Serviços (Health Checks)"

# Keycloak
KC_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${KEYCLOAK_BASE}/health/ready" || echo "DOWN")
check "Keycloak Server (:8080/health/ready)" "200" "$KC_STATUS"

# OIDC Discovery
OIDC_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$WELL_KNOWN_URL" || echo "DOWN")
check "OIDC Discovery Endpoint (.well-known)" "200" "$OIDC_STATUS"

# Sample A
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${SAMPLE_A_URL}/health" || echo "DOWN")
check "Sample A: api-simples (:8001/health)" "200" "$API_STATUS"

# Sample B
FE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${SAMPLE_B_URL}/" || echo "DOWN")
check "Sample B: frontend-pkce (:5173/)" "200" "$FE_STATUS"

# Sample C BFF
BFF_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${SAMPLE_C_BFF_URL}/health" || echo "DOWN")
check "Sample C: bff (:8002/health)" "200" "$BFF_STATUS"

# Sample C docs-service
DOCS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${SAMPLE_C_DOCS_URL}/health" || echo "DOWN")
check "Sample C: docs-service (:8003/health)" "200" "$DOCS_STATUS"

if [ "$KC_STATUS" != "200" ] || [ "$API_STATUS" != "200" ] || [ "$BFF_STATUS" != "200" ] || [ "$DOCS_STATUS" != "200" ]; then
    echo -e "\n${RED}✗ Erro: Um ou mais serviços essenciais não estão operacionais.${RESET}"
    echo -e "${YELLOW}Dica: Execute 'docker compose up --build -d' antes de rodar os testes.${RESET}\n"
    exit 1
fi

# ── Fase 1: Emissão de Tokens & Claims no Keycloak ───────────────────────────

log_section "Fase 1: Emissão de Tokens (Password Grant & Client Credentials)"

ALICE_TOKEN=$(get_user_token "alice" "alice123")
BOB_TOKEN=$(get_user_token "bob" "bob123")
CAROL_TOKEN=$(get_user_token "carol" "carol123")
BOB_READ_TOKEN=$(get_user_token "bob" "bob123" "openid documents:read")
BFF_SERVICE_TOKEN=$(get_service_token "bff-client" "$BFF_CLIENT_SECRET")

check_condition "Emissão de token para alice (admin + write scope)" "$([ -n "$ALICE_TOKEN" ] && echo true || echo false)"
check_condition "Emissão de token para bob (editor + write scope)" "$([ -n "$BOB_TOKEN" ] && echo true || echo false)"
check_condition "Emissão de token para carol (viewer + write scope)" "$([ -n "$CAROL_TOKEN" ] && echo true || echo false)"
check_condition "Emissão de token para bob (apenas scope read)" "$([ -n "$BOB_READ_TOKEN" ] && echo true || echo false)"
check_condition "Emissão de token M2M Client Credentials (bff-client)" "$([ -n "$BFF_SERVICE_TOKEN" ] && echo true || echo false)"

# Validando Claims
ALICE_ROLES=$(decode_token_claim "$ALICE_TOKEN" "realm_access.roles")
BOB_ROLES=$(decode_token_claim "$BOB_TOKEN" "realm_access.roles")
CAROL_ROLES=$(decode_token_claim "$CAROL_TOKEN" "realm_access.roles")
BFF_AZP=$(decode_token_claim "$BFF_SERVICE_TOKEN" "azp")

check_condition "Role 'admin' presente no token da Alice: ${ALICE_ROLES}" "$(echo "$ALICE_ROLES" | grep -q '"admin"' && echo true || echo false)"
check_condition "Role 'editor' presente no token do Bob: ${BOB_ROLES}" "$(echo "$BOB_ROLES" | grep -q '"editor"' && echo true || echo false)"
check_condition "Role 'viewer' presente no token da Carol: ${CAROL_ROLES}" "$(echo "$CAROL_ROLES" | grep -q '"viewer"' && echo true || echo false)"
check_condition "Claim 'azp' == 'bff-client' no token de serviço M2M: ${BFF_AZP}" "$([ "$BFF_AZP" = "bff-client" ] && echo true || echo false)"

# ── Fase 2: Sample A (api-simples:8001) ──────────────────────────────────────

log_section "Fase 2: Sample A (api-simples) — Validação JWT, RBAC & Scopes"

# 2.1 Autenticação e 401
check "GET /documents sem token → 401 Unauthorized" "401" "$(http_status GET "${SAMPLE_A_URL}/documents")"
check "GET /documents com token inválido → 401 Unauthorized" "401" "$(http_status GET "${SAMPLE_A_URL}/documents" "token_invalido_123")"
check "POST /documents sem token → 401 Unauthorized" "401" "$(http_status POST "${SAMPLE_A_URL}/documents" "" '{"title":"x","content":"x"}')"
check "DELETE /documents/1 sem token → 401 Unauthorized" "401" "$(http_status DELETE "${SAMPLE_A_URL}/documents/1")"

# 2.2 RBAC Leitura (GET /documents)
check "Alice (admin) GET /documents → 200 OK" "200" "$(http_status GET "${SAMPLE_A_URL}/documents" "$ALICE_TOKEN")"
check "Bob (editor) GET /documents → 200 OK" "200" "$(http_status GET "${SAMPLE_A_URL}/documents" "$BOB_TOKEN")"
check "Carol (viewer) GET /documents → 200 OK" "200" "$(http_status GET "${SAMPLE_A_URL}/documents" "$CAROL_TOKEN")"

# Filtro por owner
ALICE_DOC_COUNT=$(curl -s -H "Authorization: Bearer $ALICE_TOKEN" "${SAMPLE_A_URL}/documents" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
BOB_DOC_COUNT=$(curl -s -H "Authorization: Bearer $BOB_TOKEN" "${SAMPLE_A_URL}/documents" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
CAROL_DOC_COUNT=$(curl -s -H "Authorization: Bearer $CAROL_TOKEN" "${SAMPLE_A_URL}/documents" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")

check_condition "Filtro RBAC: Alice (admin) vê mais docs (${ALICE_DOC_COUNT}) que Bob (${BOB_DOC_COUNT}) e Carol (${CAROL_DOC_COUNT})" \
    "$([ "$ALICE_DOC_COUNT" -gt "$BOB_DOC_COUNT" ] && [ "$ALICE_DOC_COUNT" -gt "$CAROL_DOC_COUNT" ] && echo true || echo false)"

# 2.3 RBAC Leitura por ID (GET /documents/{id})
check "Alice (admin) acessa doc do bob (id=2) → 200 OK" "200" "$(http_status GET "${SAMPLE_A_URL}/documents/2" "$ALICE_TOKEN")"
check "Alice (admin) acessa doc da carol (id=3) → 200 OK" "200" "$(http_status GET "${SAMPLE_A_URL}/documents/3" "$ALICE_TOKEN")"
check "Bob (editor) acessa seu próprio doc (id=2) → 200 OK" "200" "$(http_status GET "${SAMPLE_A_URL}/documents/2" "$BOB_TOKEN")"
check "Bob (editor) acessa doc da carol (id=3) → 403 Forbidden" "403" "$(http_status GET "${SAMPLE_A_URL}/documents/3" "$BOB_TOKEN")"
check "Carol (viewer) acessa seu próprio doc (id=3) → 200 OK" "200" "$(http_status GET "${SAMPLE_A_URL}/documents/3" "$CAROL_TOKEN")"
check "Carol (viewer) acessa doc do bob (id=2) → 403 Forbidden" "403" "$(http_status GET "${SAMPLE_A_URL}/documents/2" "$CAROL_TOKEN")"
check "Busca de documento inexistente (id=999999) → 404 Not Found" "404" "$(http_status GET "${SAMPLE_A_URL}/documents/999999" "$ALICE_TOKEN")"

# 2.4 RBAC & Scopes Escrita (POST /documents)
DOC_BODY='{"title":"Doc Validação E2E","content":"Conteúdo criado pelo script de teste"}'

check "Alice (admin + scope write) cria documento → 201 Created" "201" "$(http_status POST "${SAMPLE_A_URL}/documents" "$ALICE_TOKEN" "$DOC_BODY")"
check "Bob (editor + scope write) cria documento → 201 Created" "201" "$(http_status POST "${SAMPLE_A_URL}/documents" "$BOB_TOKEN" "$DOC_BODY")"
check "Bob (editor SEM scope write) cria documento → 403 Forbidden (Scope)" "403" "$(http_status POST "${SAMPLE_A_URL}/documents" "$BOB_READ_TOKEN" "$DOC_BODY")"
check "Carol (viewer + scope write) cria documento → 403 Forbidden (Role)" "403" "$(http_status POST "${SAMPLE_A_URL}/documents" "$CAROL_TOKEN" "$DOC_BODY")"

# 2.5 RBAC Deleção (DELETE /documents/{id})
TEMP_DOC_RESP=$(curl -s -X POST "${SAMPLE_A_URL}/documents" \
    -H "Authorization: Bearer $ALICE_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"title":"Doc para deletar","content":"Temp"}')
TEMP_DOC_ID=$(echo "$TEMP_DOC_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))")

if [ -n "$TEMP_DOC_ID" ]; then
    check "Bob (editor) tenta deletar doc ${TEMP_DOC_ID} → 403 Forbidden" "403" "$(http_status DELETE "${SAMPLE_A_URL}/documents/${TEMP_DOC_ID}" "$BOB_TOKEN")"
    check "Carol (viewer) tenta deletar doc ${TEMP_DOC_ID} → 403 Forbidden" "403" "$(http_status DELETE "${SAMPLE_A_URL}/documents/${TEMP_DOC_ID}" "$CAROL_TOKEN")"
    check "Alice (admin) deleta doc ${TEMP_DOC_ID} → 204 No Content" "204" "$(http_status DELETE "${SAMPLE_A_URL}/documents/${TEMP_DOC_ID}" "$ALICE_TOKEN")"
    check "Alice (admin) deleta novamente doc ${TEMP_DOC_ID} → 404 Not Found" "404" "$(http_status DELETE "${SAMPLE_A_URL}/documents/${TEMP_DOC_ID}" "$ALICE_TOKEN")"
fi

# 2.6 Endpoint /me & Token Introspection
check "GET /me com Alice → 200 OK" "200" "$(http_status GET "${SAMPLE_A_URL}/me" "$ALICE_TOKEN")"
check "GET /me com Bob → 200 OK" "200" "$(http_status GET "${SAMPLE_A_URL}/me" "$BOB_TOKEN")"
check "GET /documents-introspect (RFC 7662) com Alice → 200 OK" "200" "$(http_status GET "${SAMPLE_A_URL}/documents-introspect" "$ALICE_TOKEN")"

# ── Fase 3: Sample B (frontend-pkce:5173) ─────────────────────────────────────

log_section "Fase 3: Sample B (frontend-pkce) — Servidor & Fluxo PKCE"

FE_PAGE_CONTENT=$(curl -s "${SAMPLE_B_URL}/")
check_condition "Frontend React HTML retornado com sucesso" "$(echo "$FE_PAGE_CONTENT" | grep -q "html" && echo true || echo false)"

AUTH_ENDPOINT="${KEYCLOAK_BASE}/realms/${REALM}/protocol/openid-connect/auth"
AUTH_ENDPOINT_STATUS=$(curl -s -L -o /dev/null -w "%{http_code}" "${AUTH_ENDPOINT}?response_type=code&client_id=frontend-pkce&redirect_uri=http://localhost:5173" || echo "DOWN")
check "Endpoint de Autorização PKCE responde (redirect para tela de login do Keycloak)" "200" "$AUTH_ENDPOINT_STATUS"

# ── Fase 4: Sample C (bff:8002 & docs-service:8003) ──────────────────────────

log_section "Fase 4: Sample C (BFF + docs-service) — M2M & Isolamento"

# 4.1 Isolamento do docs-service downstream
check "docs-service direto sem token → 401 Unauthorized" "401" "$(http_status GET "${SAMPLE_C_DOCS_URL}/internal/documents")"
check "docs-service direto com token de usuário (Alice) → 403 Forbidden (azp mismatch)" "403" "$(http_status GET "${SAMPLE_C_DOCS_URL}/internal/documents" "$ALICE_TOKEN")"
check "docs-service direto com token de usuário (Bob) → 403 Forbidden (azp mismatch)" "403" "$(http_status GET "${SAMPLE_C_DOCS_URL}/internal/documents" "$BOB_TOKEN")"
check "docs-service direto com token M2M (bff-client) → 200 OK" "200" "$(http_status GET "${SAMPLE_C_DOCS_URL}/internal/documents" "$BFF_SERVICE_TOKEN")"

# 4.2 BFF Proxy (/bff/documents)
check "BFF /bff/documents sem token → 401 Unauthorized" "401" "$(http_status GET "${SAMPLE_C_BFF_URL}/bff/documents")"
check "Alice chama BFF /bff/documents → 200 OK (BFF chama docs-service via M2M)" "200" "$(http_status GET "${SAMPLE_C_BFF_URL}/bff/documents" "$ALICE_TOKEN")"
check "Bob chama BFF /bff/documents → 200 OK (BFF chama docs-service via M2M)" "200" "$(http_status GET "${SAMPLE_C_BFF_URL}/bff/documents" "$BOB_TOKEN")"
check "Carol chama BFF /bff/documents → 200 OK (BFF chama docs-service via M2M)" "200" "$(http_status GET "${SAMPLE_C_BFF_URL}/bff/documents" "$CAROL_TOKEN")"

# 4.3 BFF Debug Tokens Comparison
DEBUG_RESP=$(curl -s -H "Authorization: Bearer $ALICE_TOKEN" "${SAMPLE_C_BFF_URL}/bff/debug/tokens")
check_condition "Endpoint /bff/debug/tokens compara User Token e Service Token M2M" \
    "$(echo "$DEBUG_RESP" | grep -q "user_token" && echo "$DEBUG_RESP" | grep -q "service_token" && echo true || echo false)"

# ── Fase 5: Resumo e Resultado Final ──────────────────────────────────────────

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
TOTAL=$((PASS + FAIL))

echo ""
echo -e "${BOLD}${MAGENTA}======================================================================${RESET}"
echo -e "${BOLD}${MAGENTA}                   RESUMO DA VALIDAÇÃO END-TO-END                     ${RESET}"
echo -e "${BOLD}${MAGENTA}======================================================================${RESET}"
echo -e "Duração da execução: ${DURATION}s"
echo -e "Total de testes executados: ${TOTAL}"
echo -e "Testes com sucesso: ${GREEN}${PASS}${RESET}"
echo -e "Testes com falha:   $([ "$FAIL" -gt 0 ] && echo -e "${RED}${FAIL}${RESET}" || echo -e "${GREEN}0${RESET}")"
echo ""

if [ "$FAIL" -eq 0 ]; then
    echo -e "${BOLD}${GREEN}======================================================================${RESET}"
    echo -e "${BOLD}${GREEN}  ✓ TODOS OS ${TOTAL} TESTES PASSARAM COM SUCESSO EM TODOS OS SAMPLES!  ${RESET}"
    echo -e "${BOLD}${GREEN}======================================================================${RESET}"
    echo ""
    exit 0
else
    echo -e "${BOLD}${RED}======================================================================${RESET}"
    echo -e "${BOLD}${RED}  ✗ OCORRERAM ${FAIL} FALHAS NA VALIDAÇÃO DOS SAMPLES. VERIFIQUE OS LOGS.  ${RESET}"
    echo -e "${BOLD}${RED}======================================================================${RESET}"
    echo ""
    exit 1
fi
