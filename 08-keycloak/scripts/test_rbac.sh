#!/usr/bin/env bash
# =============================================================================
# test_rbac.sh — Card 8: Validação de RBAC com os 3 usuários
#
# Testa todos os endpoints de /documents com alice (admin), bob (editor)
# e carol (viewer), validando os status HTTP esperados para cada combinação.
#
# Uso:
#   bash samples/api-simples/scripts/test_rbac.sh
#
# Pré-requisitos:
#   - docker compose up -d (Keycloak + api-simples rodando)
#   - curl e python3 disponíveis no PATH
# =============================================================================

set -euo pipefail

# ── Configuração ──────────────────────────────────────────────────────────────

KEYCLOAK_URL="http://localhost:8080/realms/distributed-systems/protocol/openid-connect/token"
API_URL="http://localhost:8001"
CLIENT_ID="api-simples"
CLIENT_SECRET="GZYImUZPV2W7tWzsQKTbpzdNFI2eLdGC"

# ── Cores ─────────────────────────────────────────────────────────────────────

GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
CYAN="\033[0;36m"
BOLD="\033[1m"
RESET="\033[0m"

# ── Contadores ────────────────────────────────────────────────────────────────

PASS=0
FAIL=0

# ── Funções auxiliares ────────────────────────────────────────────────────────

get_token() {
    local username="$1"
    local password="$2"
    curl -s -X POST "$KEYCLOAK_URL" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "grant_type=password&client_id=${CLIENT_ID}&client_secret=${CLIENT_SECRET}&username=${username}&password=${password}" \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token', ''))"
}

# check <descrição> <status_esperado> <status_real>
check() {
    local desc="$1"
    local expected="$2"
    local actual="$3"

    if [ "$actual" = "$expected" ]; then
        echo -e "  ${GREEN}✓ PASS${RESET} ${desc} → ${actual}"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}✗ FAIL${RESET} ${desc} → esperado ${expected}, obtido ${actual}"
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

# ── Início ────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${CYAN}============================================================${RESET}"
echo -e "${BOLD}${CYAN} Card 8 — Validação de RBAC — api-simples${RESET}"
echo -e "${BOLD}${CYAN} API: ${API_URL}${RESET}"
echo -e "${BOLD}${CYAN}============================================================${RESET}"

# ── Verifica se a API está no ar ──────────────────────────────────────────────

echo ""
echo -e "${BOLD}── Verificando saúde da API ──────────────────────────────────${RESET}"
HEALTH=$(curl -sf "${API_URL}/health" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','?'))" 2>/dev/null || echo "DOWN")
if [ "$HEALTH" = "ok" ]; then
    echo -e "  ${GREEN}✓${RESET} api-simples está no ar"
else
    echo -e "  ${RED}✗ api-simples não está respondendo. Rode: docker compose up -d${RESET}"
    exit 1
fi

# ── Obtém tokens ──────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}── Obtendo tokens do Keycloak ────────────────────────────────${RESET}"
ALICE_TOKEN=$(get_token "alice" "alice123")
BOB_TOKEN=$(get_token "bob" "bob123")
CAROL_TOKEN=$(get_token "carol" "carol123")

[ -n "$ALICE_TOKEN" ] && echo -e "  ${GREEN}✓${RESET} Token alice  (admin)  obtido" || { echo -e "  ${RED}✗ Falha ao obter token para alice${RESET}"; exit 1; }
[ -n "$BOB_TOKEN"   ] && echo -e "  ${GREEN}✓${RESET} Token bob    (editor) obtido" || { echo -e "  ${RED}✗ Falha ao obter token para bob${RESET}"; exit 1; }
[ -n "$CAROL_TOKEN" ] && echo -e "  ${GREEN}✓${RESET} Token carol  (viewer) obtido" || { echo -e "  ${RED}✗ Falha ao obter token para carol${RESET}"; exit 1; }

# ── Testes sem autenticação ───────────────────────────────────────────────────

echo ""
echo -e "${BOLD}── Sem token (deve ser 401) ──────────────────────────────────${RESET}"
check "GET /documents sem token       → 401" "401" "$(http_status GET "${API_URL}/documents")"
check "POST /documents sem token      → 401" "401" "$(http_status POST "${API_URL}/documents" "" '{"title":"x","content":"x"}')"
check "DELETE /documents/1 sem token  → 401" "401" "$(http_status DELETE "${API_URL}/documents/1")"

# ── GET /documents ────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}── GET /documents ────────────────────────────────────────────${RESET}"
echo -e "${YELLOW}   admin vê todos | editor/viewer veem apenas os próprios${RESET}"

check "alice (admin)  → 200" "200" "$(http_status GET "${API_URL}/documents" "$ALICE_TOKEN")"
check "bob   (editor) → 200" "200" "$(http_status GET "${API_URL}/documents" "$BOB_TOKEN")"
check "carol (viewer) → 200" "200" "$(http_status GET "${API_URL}/documents" "$CAROL_TOKEN")"

# Valida que alice vê mais documentos que bob e carol
ALICE_COUNT=$(curl -s -H "Authorization: Bearer $ALICE_TOKEN" "${API_URL}/documents" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
BOB_COUNT=$(curl -s -H "Authorization: Bearer $BOB_TOKEN" "${API_URL}/documents" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
CAROL_COUNT=$(curl -s -H "Authorization: Bearer $CAROL_TOKEN" "${API_URL}/documents" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")

echo -e "  ${CYAN}ℹ${RESET}  alice vê ${ALICE_COUNT} doc(s) | bob vê ${BOB_COUNT} doc(s) | carol vê ${CAROL_COUNT} doc(s)"

if [ "$ALICE_COUNT" -gt "$BOB_COUNT" ] && [ "$ALICE_COUNT" -gt "$CAROL_COUNT" ]; then
    echo -e "  ${GREEN}✓ PASS${RESET} Filtro por role funcionando: admin vê mais documentos que editor/viewer"
    PASS=$((PASS + 1))
else
    echo -e "  ${RED}✗ FAIL${RESET} Filtro por role com problema: alice deveria ver mais documentos"
    FAIL=$((FAIL + 1))
fi

# ── GET /documents/{id} ───────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}── GET /documents/{id} ───────────────────────────────────────${RESET}"
echo -e "${YELLOW}   admin acessa qualquer | editor/viewer só acessam os próprios${RESET}"

# Busca IDs reais de documentos de cada usuário consultando como admin
ALICE_SUB=$(echo "$ALICE_TOKEN" | python3 -c "
import sys,base64,json
t=sys.stdin.read().strip(); p=t.split('.')[1]; p+='='*(4-len(p)%4)
print(json.loads(base64.urlsafe_b64decode(p))['sub'])
")
BOB_SUB=$(echo "$BOB_TOKEN" | python3 -c "
import sys,base64,json
t=sys.stdin.read().strip(); p=t.split('.')[1]; p+='='*(4-len(p)%4)
print(json.loads(base64.urlsafe_b64decode(p))['sub'])
")
CAROL_SUB=$(echo "$CAROL_TOKEN" | python3 -c "
import sys,base64,json
t=sys.stdin.read().strip(); p=t.split('.')[1]; p+='='*(4-len(p)%4)
print(json.loads(base64.urlsafe_b64decode(p))['sub'])
")

# Admin busca todos os documentos para encontrar IDs por owner
ALL_DOCS=$(curl -s -H "Authorization: Bearer $ALICE_TOKEN" "${API_URL}/documents")

# Encontra um doc da alice, um do bob e um da carol (se existir)
ALICE_DOC_ID=$(echo "$ALL_DOCS" | python3 -c "
import sys,json; docs=json.load(sys.stdin)
m=[d['id'] for d in docs if d['owner_id']=='$ALICE_SUB']
print(m[0] if m else '')
")
BOB_DOC_ID=$(echo "$ALL_DOCS" | python3 -c "
import sys,json; docs=json.load(sys.stdin)
m=[d['id'] for d in docs if d['owner_id']=='$BOB_SUB']
print(m[0] if m else '')
")
CAROL_DOC_ID=$(echo "$ALL_DOCS" | python3 -c "
import sys,json; docs=json.load(sys.stdin)
m=[d['id'] for d in docs if d['owner_id']=='$CAROL_SUB']
print(m[0] if m else '')
")

echo -e "  ${CYAN}ℹ${RESET}  Doc da alice: id=${ALICE_DOC_ID:-N/A} | Doc do bob: id=${BOB_DOC_ID:-N/A} | Doc da carol: id=${CAROL_DOC_ID:-N/A}"

# Admin acessa qualquer documento
if [ -n "$BOB_DOC_ID" ]; then
    check "alice (admin)  acessa doc do bob (id=${BOB_DOC_ID})   → 200" "200" "$(http_status GET "${API_URL}/documents/${BOB_DOC_ID}" "$ALICE_TOKEN")"
fi
if [ -n "$CAROL_DOC_ID" ]; then
    check "alice (admin)  acessa doc da carol (id=${CAROL_DOC_ID}) → 200" "200" "$(http_status GET "${API_URL}/documents/${CAROL_DOC_ID}" "$ALICE_TOKEN")"
fi

# Editor acessa o próprio, 403 no da carol
if [ -n "$BOB_DOC_ID" ]; then
    check "bob   (editor) acessa seu doc (id=${BOB_DOC_ID})      → 200" "200" "$(http_status GET "${API_URL}/documents/${BOB_DOC_ID}" "$BOB_TOKEN")"
fi
if [ -n "$CAROL_DOC_ID" ]; then
    check "bob   (editor) acessa doc da carol (id=${CAROL_DOC_ID}) → 403" "403" "$(http_status GET "${API_URL}/documents/${CAROL_DOC_ID}" "$BOB_TOKEN")"
fi

# Viewer acessa o próprio, 403 no do bob
if [ -n "$CAROL_DOC_ID" ]; then
    check "carol (viewer) acessa seu doc (id=${CAROL_DOC_ID})    → 200" "200" "$(http_status GET "${API_URL}/documents/${CAROL_DOC_ID}" "$CAROL_TOKEN")"
fi
if [ -n "$BOB_DOC_ID" ]; then
    check "carol (viewer) acessa doc do bob (id=${BOB_DOC_ID})   → 403" "403" "$(http_status GET "${API_URL}/documents/${BOB_DOC_ID}" "$CAROL_TOKEN")"
fi

# Doc inexistente
check "qualquer user  acessa doc 999999 (inexistente) → 404" "404" "$(http_status GET "${API_URL}/documents/999999" "$ALICE_TOKEN")"


# ── POST /documents ───────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}── POST /documents ───────────────────────────────────────────${RESET}"
echo -e "${YELLOW}   editor e admin criam | viewer recebe 403${RESET}"

DOC_PAYLOAD='{"title":"Documento de teste RBAC","content":"Criado pelo script de validação"}'

check "alice (admin)  cria documento → 201" "201" "$(http_status POST "${API_URL}/documents" "$ALICE_TOKEN" "$DOC_PAYLOAD")"
check "bob   (editor) cria documento → 201" "201" "$(http_status POST "${API_URL}/documents" "$BOB_TOKEN" "$DOC_PAYLOAD")"
check "carol (viewer) cria documento → 403" "403" "$(http_status POST "${API_URL}/documents" "$CAROL_TOKEN" "$DOC_PAYLOAD")"

# Valida que o owner_id do doc criado por bob é o sub do bob
BOB_NEW_DOC=$(curl -s -X POST "${API_URL}/documents" \
    -H "Authorization: Bearer $BOB_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"title":"Doc owner_id test","content":"Verificando sub"}')

BOB_SUB=$(echo "$BOB_TOKEN" | python3 -c "
import sys,base64,json
t=sys.stdin.read().strip()
p=t.split('.')[1]; p+='='*(4-len(p)%4)
print(json.loads(base64.urlsafe_b64decode(p))['sub'])
")
BOB_NEW_OWNER=$(echo "$BOB_NEW_DOC" | python3 -c "import sys,json; print(json.load(sys.stdin).get('owner_id','?'))")

if [ "$BOB_NEW_OWNER" = "$BOB_SUB" ]; then
    echo -e "  ${GREEN}✓ PASS${RESET} owner_id preenchido com sub do JWT (bob)"
    PASS=$((PASS + 1))
else
    echo -e "  ${RED}✗ FAIL${RESET} owner_id incorreto: esperado ${BOB_SUB}, obtido ${BOB_NEW_OWNER}"
    FAIL=$((FAIL + 1))
fi

# ── DELETE /documents ─────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}── DELETE /documents/{id} ────────────────────────────────────${RESET}"
echo -e "${YELLOW}   somente admin pode deletar${RESET}"

# Cria um doc temporário para deletar
TEMP_DOC=$(curl -s -X POST "${API_URL}/documents" \
    -H "Authorization: Bearer $ALICE_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"title":"Temp para deletar","content":"Será deletado"}')
TEMP_ID=$(echo "$TEMP_DOC" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

check "bob   (editor) deleta doc ${TEMP_ID} → 403" "403" "$(http_status DELETE "${API_URL}/documents/${TEMP_ID}" "$BOB_TOKEN")"
check "carol (viewer) deleta doc ${TEMP_ID} → 403" "403" "$(http_status DELETE "${API_URL}/documents/${TEMP_ID}" "$CAROL_TOKEN")"
check "alice (admin)  deleta doc ${TEMP_ID} → 204" "204" "$(http_status DELETE "${API_URL}/documents/${TEMP_ID}" "$ALICE_TOKEN")"
check "alice (admin)  deleta doc ${TEMP_ID} de novo → 404" "404" "$(http_status DELETE "${API_URL}/documents/${TEMP_ID}" "$ALICE_TOKEN")"

# ── GET /me ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}── GET /me ────────────────────────────────────────────────────${RESET}"
echo -e "${YELLOW}   qualquer usuário autenticado acessa${RESET}"

check "alice (admin)  GET /me → 200" "200" "$(http_status GET "${API_URL}/me" "$ALICE_TOKEN")"
check "bob   (editor) GET /me → 200" "200" "$(http_status GET "${API_URL}/me" "$BOB_TOKEN")"
check "carol (viewer) GET /me → 200" "200" "$(http_status GET "${API_URL}/me" "$CAROL_TOKEN")"

# ── Resultado final ───────────────────────────────────────────────────────────

TOTAL=$((PASS + FAIL))
echo ""
echo -e "${BOLD}${CYAN}============================================================${RESET}"
if [ "$FAIL" -eq 0 ]; then
    echo -e "${BOLD}${GREEN} RESULTADO: ${PASS}/${TOTAL} testes passaram ✓${RESET}"
else
    echo -e "${BOLD}${RED} RESULTADO: ${PASS}/${TOTAL} passaram | ${FAIL} falharam ✗${RESET}"
fi
echo -e "${BOLD}${CYAN}============================================================${RESET}"
echo ""

exit $FAIL
