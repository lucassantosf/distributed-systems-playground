#!/usr/bin/env bash
set -uo pipefail

BASE_USER="http://localhost:8001"
BASE_PRODUCT="http://localhost:8002"
BASE_ORDER="http://localhost:8003"
TAG="e2e-$(date +%s)"
PASS=0
FAIL=0

green() { printf '\033[32m%s\033[0m\n' "$1"; }
red()   { printf '\033[31m%s\033[0m\n' "$1"; }
bold()  { printf '\033[1m%s\033[0m\n' "$1"; }

assert() {
    local label="$1" expected="$2" actual="$3"
    if [[ "$actual" == "$expected" ]]; then
        green "  PASS  $label"
        ((PASS++))
    else
        red "  FAIL  $label (expected: $expected, got: $actual)"
        ((FAIL++))
    fi
}

# curl_req METHOD URL [DATA] — returns "CODE:BODY"
curl_req() {
    local method="$1" url="$2" data="${3:-}"
    if [ -n "$data" ]; then
        curl -s -o /tmp/e2e_body.txt -w '%{http_code}' -X "$method" "$url" \
            -H 'Content-Type: application/json' -d "$data"
    else
        curl -s -o /tmp/e2e_body.txt -w '%{http_code}' -X "$method" "$url"
    fi
    local code=$?
    # body is already in /tmp/e2e_body.txt
    return $code
}

bold "=== E2E: Full Order Flow ==="
echo ""

# =============================================
bold "1. Create user"
# =============================================
EMAIL="${TAG}@test.com"
CODE=$(curl_req POST "$BASE_USER/users/" "{\"email\":\"$EMAIL\",\"name\":\"E2E User\",\"age\":25}")
USER_BODY=$(cat /tmp/e2e_body.txt)
USER_ID=$(echo "$USER_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
assert "create user HTTP 201" "201" "$CODE"
echo "  user_id: $USER_ID"
echo ""

# =============================================
bold "2. Create product with stock"
# =============================================
CODE=$(curl_req POST "$BASE_PRODUCT/products/" '{"name":"E2E Widget","description":"Test product","price":19.99,"stock":10}')
PROD_BODY=$(cat /tmp/e2e_body.txt)
PROD_ID=$(echo "$PROD_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
assert "create product HTTP 201" "201" "$CODE"
echo "  product_id: $PROD_ID"
echo ""

# =============================================
bold "3. Create order (happy path)"
# =============================================
CODE=$(curl_req POST "$BASE_ORDER/orders/" "{\"user_id\":\"$USER_ID\",\"items\":[{\"product_id\":\"$PROD_ID\",\"quantity\":3}]}")
ORDER_BODY=$(cat /tmp/e2e_body.txt)
ORDER_ID=$(echo "$ORDER_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
TOTAL=$(echo "$ORDER_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['total_price'])")
STATUS=$(echo "$ORDER_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
assert "create order HTTP 201" "201" "$CODE"
assert "order status = pending" "pending" "$STATUS"
assert "total_price = 59.97 (3 x 19.99)" "59.97" "$TOTAL"
echo "  order_id: $ORDER_ID"
echo ""

# =============================================
bold "4. Verify GET /orders/{order_id}"
# =============================================
CODE=$(curl_req GET "$BASE_ORDER/orders/$ORDER_ID")
GET_BODY=$(cat /tmp/e2e_body.txt)
GET_ID=$(echo "$GET_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
GET_STATUS=$(echo "$GET_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
assert "GET order returns 200" "200" "$CODE"
assert "GET order returns same id" "$ORDER_ID" "$GET_ID"
assert "GET order status = pending" "pending" "$GET_STATUS"
echo ""

# =============================================
bold "5. Verify GET /orders/user/{user_id}"
# =============================================
CODE=$(curl_req GET "$BASE_ORDER/orders/user/$USER_ID")
USER_ORDERS_BODY=$(cat /tmp/e2e_body.txt)
USER_ORDERS_COUNT=$(echo "$USER_ORDERS_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])")
assert "orders/user returns 200" "200" "$CODE"
assert "user has 1 order" "1" "$USER_ORDERS_COUNT"
echo ""

# =============================================
bold "6. Verify GET /orders (list all)"
# =============================================
CODE=$(curl_req GET "$BASE_ORDER/orders/")
ALL_ORDERS_BODY=$(cat /tmp/e2e_body.txt)
ALL_TOTAL=$(echo "$ALL_ORDERS_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])")
assert "list orders returns 200" "200" "$CODE"
[[ "$ALL_TOTAL" -ge 1 ]] && green "  PASS  list orders returns >= 1" && ((PASS++)) \
    || { red "  FAIL  list orders total < 1"; ((FAIL++)); }
echo ""

# =============================================
bold "7. Update order status"
# =============================================
CODE=$(curl_req PATCH "$BASE_ORDER/orders/$ORDER_ID/status?status=confirmed")
UPD_BODY=$(cat /tmp/e2e_body.txt)
UPD_STATUS=$(echo "$UPD_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
assert "update status returns 200" "200" "$CODE"
assert "update status to confirmed" "confirmed" "$UPD_STATUS"

CODE=$(curl_req GET "$BASE_ORDER/orders/$ORDER_ID")
GET2_BODY=$(cat /tmp/e2e_body.txt)
GET2_STATUS=$(echo "$GET2_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
assert "GET after update shows confirmed" "confirmed" "$GET2_STATUS"
echo ""

# =============================================
bold "8. Error: non-existent user"
# =============================================
FAKE_ID="00000000-0000-0000-0000-000000000000"
CODE=$(curl_req POST "$BASE_ORDER/orders/" "{\"user_id\":\"$FAKE_ID\",\"items\":[{\"product_id\":\"$PROD_ID\",\"quantity\":1}]}")
assert "nonexistent user returns 404" "404" "$CODE"
echo ""

# =============================================
bold "9. Error: insufficient stock"
# =============================================
CODE=$(curl_req POST "$BASE_ORDER/orders/" "{\"user_id\":\"$USER_ID\",\"items\":[{\"product_id\":\"$PROD_ID\",\"quantity\":999}]}")
assert "insufficient stock returns 409" "409" "$CODE"
echo ""

# =============================================
bold "10. Error: invalid status"
# =============================================
CODE=$(curl_req PATCH "$BASE_ORDER/orders/$ORDER_ID/status?status=invalid")
assert "invalid status returns 400" "400" "$CODE"
echo ""

# =============================================
bold "11. Health checks"
# =============================================
for svc in "$BASE_USER" "$BASE_PRODUCT" "$BASE_ORDER"; do
    CODE=$(curl_req GET "$svc/health")
    assert "$svc/health returns 200" "200" "$CODE"
done
echo ""

# =============================================
bold "12. gRPC test endpoints"
# =============================================
CODE=$(curl_req GET "$BASE_ORDER/test/user-gRPC/$EMAIL")
GRPC_USER_BODY=$(cat /tmp/e2e_body.txt)
GRPC_USER_SRC=$(echo "$GRPC_USER_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['source'])")
assert "gRPC user returns 200" "200" "$CODE"
assert "gRPC user source" "gRPC (user-service:50051)" "$GRPC_USER_SRC"

CODE=$(curl_req GET "$BASE_ORDER/test/product-gRPC/$PROD_ID")
GRPC_PROD_BODY=$(cat /tmp/e2e_body.txt)
GRPC_PROD_SRC=$(echo "$GRPC_PROD_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['source'])")
assert "gRPC product returns 200" "200" "$CODE"
assert "gRPC product source" "gRPC (product-service:50052)" "$GRPC_PROD_SRC"
echo ""

# =============================================
bold "=== Summary ==="
# =============================================
TOTAL=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ]; then
    green "All $TOTAL tests passed!"
else
    red "$FAIL of $TOTAL tests FAILED"
fi
echo ""
echo "Test data created:"
echo "  user:    $EMAIL  (id: $USER_ID)"
echo "  product: E2E Widget  (id: $PROD_ID)"
echo "  order:   (id: $ORDER_ID)"

exit $FAIL
