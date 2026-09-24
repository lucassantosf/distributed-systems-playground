#!/usr/bin/env bash
# ============================================================
# validate_full_flow.sh — Validação End-to-End do projeto BFF
#
# Testa o fluxo completo:
#   1. Health check de todos os serviços (incluindo Redis)
#   2. Endpoints diretos dos microsserviços
#   3. Composição de dados pelo BFF (GET /bff/orders, /bff/orders/{id})
#   4. Cache Redis: X-Cache MISS → HIT
#   5. Timeout (graceful degradation via order-service delay)
#   6. Graceful degradation: simula user-service fora do ar
#   7. Endpoint de comparação BFF vs. direto (/bff/users/{id}/orders)
# ============================================================

set -eo pipefail

BFF_URL="http://localhost:8000"
USER_URL="http://localhost:8001"
PRODUCT_URL="http://localhost:8002"
ORDER_URL="http://localhost:8003"

PASSED=0
FAILED=0

# ── Helpers ──────────────────────────────────────────────────────────────────

GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
CYAN="\033[0;36m"
BOLD="\033[1m"
RESET="\033[0m"

section() { echo -e "\n${BOLD}${CYAN}══ $1 ══${RESET}"; }
info()    { echo -e "  ${YELLOW}ℹ  $1${RESET}"; }

check_http() {
    local description="$1"
    local url="$2"
    local expected="${3:-200}"

    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" "$url")

    if [ "$code" -eq "$expected" ]; then
        echo -e "  ${GREEN}[PASS]${RESET} $description → HTTP $code"
        PASSED=$((PASSED + 1))
    else
        echo -e "  ${RED}[FAIL]${RESET} $description → Expected HTTP $expected, got HTTP $code"
        FAILED=$((FAILED + 1))
    fi
}

check_header() {
    local description="$1"
    local url="$2"
    local header_name="$3"
    local expected_value="$4"

    local value
    value=$(curl -s -i "$url" | grep -i "^${header_name}:" | tr -d '\r' | awk '{print $2}')

    if [ "$value" = "$expected_value" ]; then
        echo -e "  ${GREEN}[PASS]${RESET} $description → ${header_name}: $value"
        PASSED=$((PASSED + 1))
    else
        echo -e "  ${RED}[FAIL]${RESET} $description → Expected ${header_name}: $expected_value, got: '$value'"
        FAILED=$((FAILED + 1))
    fi
}

check_json_field() {
    local description="$1"
    local url="$2"
    local field="$3"
    local expected="$4"

    local value
    value=$(curl -s "$url" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$field',''))" 2>/dev/null)

    if [ "$value" = "$expected" ]; then
        echo -e "  ${GREEN}[PASS]${RESET} $description → .$field = \"$value\""
        PASSED=$((PASSED + 1))
    else
        echo -e "  ${RED}[FAIL]${RESET} $description → Expected .$field=\"$expected\", got \"$value\""
        FAILED=$((FAILED + 1))
    fi
}

wait_for() {
    local name="$1"
    local url="$2"
    local retries=20

    echo -n "  Aguardando $name"
    until curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "^200$"; do
        retries=$((retries - 1))
        if [ "$retries" -le 0 ]; then
            echo ""
            echo -e "  ${RED}[TIMEOUT]${RESET} $name não respondeu em tempo hábil em $url"
            exit 1
        fi
        echo -n "."
        sleep 1
    done
    echo -e " ${GREEN}OK${RESET}"
}

# ── 0. Aguardar serviços ──────────────────────────────────────────────────────

section "0. Aguardando serviços estarem prontos"
wait_for "BFF"             "$BFF_URL/health"
wait_for "user-service"    "$USER_URL/health"
wait_for "product-service" "$PRODUCT_URL/health"
wait_for "order-service"   "$ORDER_URL/health"

# ── 1. Health checks ─────────────────────────────────────────────────────────

section "1. Health checks"
check_http "BFF /health"              "$BFF_URL/health"
check_http "BFF /health/downstream"   "$BFF_URL/health/downstream"
check_json_field "Redis aparece no downstream" "$BFF_URL/health/downstream" "status" "ok"
check_http "user-service /health"    "$USER_URL/health"
check_http "product-service /health" "$PRODUCT_URL/health"
check_http "order-service /health"   "$ORDER_URL/health"

# ── 2. Endpoints diretos dos microsserviços ───────────────────────────────────

section "2. Endpoints diretos dos microsserviços"
check_http "user-service  GET /users"       "$USER_URL/users"
check_http "user-service  GET /users/1"     "$USER_URL/users/1"
check_http "user-service  GET /users/99"    "$USER_URL/users/99"   404
check_http "product-service GET /products"      "$PRODUCT_URL/products"
check_http "product-service GET /products/1"    "$PRODUCT_URL/products/1"
check_http "product-service GET /products/99"   "$PRODUCT_URL/products/99" 404
check_http "order-service GET /orders"      "$ORDER_URL/orders"
check_http "order-service GET /orders/1"    "$ORDER_URL/orders/1"
check_http "order-service GET /orders/99"   "$ORDER_URL/orders/99"  404

# ── 3. BFF — composição de dados ─────────────────────────────────────────────

section "3. BFF — Composição de dados"
check_http "BFF GET /bff/orders"      "$BFF_URL/bff/orders"
check_http "BFF GET /bff/orders/1"    "$BFF_URL/bff/orders/1"
check_http "BFF GET /bff/orders/2"    "$BFF_URL/bff/orders/2"
check_http "BFF GET /bff/orders/99 (Not Found)" "$BFF_URL/bff/orders/99" 404
check_http "BFF GET /bff/users/1/orders"   "$BFF_URL/bff/users/1/orders"

# Verifica que o BFF realmente une os dados (campo customer deve existir)
CUSTOMER_NAME=$(curl -s "$BFF_URL/bff/orders/1" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('customer', {}).get('name', ''))
" 2>/dev/null)
if [ -n "$CUSTOMER_NAME" ]; then
    echo -e "  ${GREEN}[PASS]${RESET} BFF GET /bff/orders/1 → customer.name = \"$CUSTOMER_NAME\""
    PASSED=$((PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${RESET} BFF GET /bff/orders/1 → customer.name está vazio"
    FAILED=$((FAILED + 1))
fi

ITEMS_COUNT=$(curl -s "$BFF_URL/bff/orders/1" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(len(d.get('items', [])))
" 2>/dev/null)
if [ "$ITEMS_COUNT" -gt 0 ] 2>/dev/null; then
    echo -e "  ${GREEN}[PASS]${RESET} BFF GET /bff/orders/1 → items[] tem $ITEMS_COUNT produto(s) compostos"
    PASSED=$((PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${RESET} BFF GET /bff/orders/1 → items[] está vazio"
    FAILED=$((FAILED + 1))
fi

# ── 4. Cache Redis: MISS → HIT ────────────────────────────────────────────────

section "4. Cache Redis (X-Cache: MISS → HIT)"
# Limpa a chave de cache garantindo MISS primeiro
docker exec redis redis-cli DEL order_detail:3 > /dev/null 2>&1 || true

check_header "1ª chamada GET /bff/orders/3 (MISS)" "$BFF_URL/bff/orders/3" "x-cache" "MISS"
check_header "2ª chamada GET /bff/orders/3 (HIT)"  "$BFF_URL/bff/orders/3" "x-cache" "HIT"

# Cache da listagem
docker exec redis redis-cli DEL orders_list > /dev/null 2>&1 || true
check_header "1ª chamada GET /bff/orders (MISS)" "$BFF_URL/bff/orders" "x-cache" "MISS"
check_header "2ª chamada GET /bff/orders (HIT)"  "$BFF_URL/bff/orders" "x-cache" "HIT"

# ── 5. Timeout (graceful degradation) ────────────────────────────────────────

section "5. Timeout — order-service com delay > 5s retorna 504"
info "Enviando delay=6s (timeout configurado em 5s)..."
TIMEOUT_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BFF_URL/bff/orders?delay=6")
if [ "$TIMEOUT_CODE" -eq 504 ]; then
    echo -e "  ${GREEN}[PASS]${RESET} GET /bff/orders?delay=6 → HTTP 504 (timeout corretamente sinalizado)"
    PASSED=$((PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${RESET} GET /bff/orders?delay=6 → Expected 504, got $TIMEOUT_CODE"
    FAILED=$((FAILED + 1))
fi

# ── 6. Graceful degradation — user-service fora do ar ─────────────────────────

section "6. Graceful degradation — user-service fora do ar"
info "Parando user-service (docker stop)..."
docker stop user-service > /dev/null 2>&1

info "Limpando cache do pedido 1 para forçar chamada downstream..."
docker exec redis redis-cli DEL order_detail:1 > /dev/null 2>&1 || true

DEGRADE_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BFF_URL/bff/orders/1")
DEGRADE_FLAG=$(curl -s "$BFF_URL/bff/orders/1" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('is_degraded', ''))
" 2>/dev/null)

docker start user-service > /dev/null 2>&1
info "user-service restaurado."

if [ "$DEGRADE_CODE" -eq 200 ] && [ "$DEGRADE_FLAG" = "True" ]; then
    echo -e "  ${GREEN}[PASS]${RESET} Degradação aceita: HTTP $DEGRADE_CODE com is_degraded=True (user-service indisponível)"
    PASSED=$((PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${RESET} Esperado HTTP 200 com is_degraded=True, obtido HTTP $DEGRADE_CODE / is_degraded=$DEGRADE_FLAG"
    FAILED=$((FAILED + 1))
fi

# ── Resultado final ───────────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════════"
echo -e "${BOLD} RESULTADO FINAL${RESET}"
echo "════════════════════════════════════════════"
echo -e "  ${GREEN}Passou:  $PASSED${RESET}"
if [ "$FAILED" -gt 0 ]; then
    echo -e "  ${RED}Falhou:  $FAILED${RESET}"
    echo "════════════════════════════════════════════"
    exit 1
else
    echo -e "  ${RED}Falhou:  0${RESET}"
    echo "════════════════════════════════════════════"
    echo -e "  ${GREEN}${BOLD}✓ FLUXO COMPLETO VALIDADO COM SUCESSO!${RESET}"
    exit 0
fi
