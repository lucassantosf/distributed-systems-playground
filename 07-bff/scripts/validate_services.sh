#!/usr/bin/env bash
set -e

BASE_USER_URL="http://localhost:8001"
BASE_PRODUCT_URL="http://localhost:8002"
BASE_ORDER_URL="http://localhost:8003"

FAILED=0

wait_for_service() {
    local name="$1"
    local url="$2"
    local retries=10
    local wait_sec=1
    
    until curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "^200$"; do
        retries=$((retries - 1))
        if [ "$retries" -le 0 ]; then
            echo "[ERROR] Timed out waiting for $name to respond at $url"
            exit 1
        fi
        sleep "$wait_sec"
    done
}

check_endpoint() {
    local name="$1"
    local url="$2"
    local expected_code="$3"
    
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    
    if [ "$code" -eq "$expected_code" ]; then
        echo "[PASS] $name -> HTTP $code"
    else
        echo "[FAIL] $name -> Expected HTTP $expected_code, got $code"
        FAILED=1
    fi
}

echo "=========================================="
echo " Validating Downstream Services"
echo "=========================================="

echo "Waiting for services to be ready..."
wait_for_service "User Service" "$BASE_USER_URL/health"
wait_for_service "Product Service" "$BASE_PRODUCT_URL/health"
wait_for_service "Order Service" "$BASE_ORDER_URL/health"

echo ""
echo "--- 1. User Service (Port 8001) ---"
check_endpoint "User Service Health" "$BASE_USER_URL/health" 200
check_endpoint "List Users" "$BASE_USER_URL/users" 200
check_endpoint "Get User 1" "$BASE_USER_URL/users/1" 200
check_endpoint "Get User 99 (Not Found)" "$BASE_USER_URL/users/99" 404

echo ""
echo "--- 2. Product Service (Port 8002) ---"
check_endpoint "Product Service Health" "$BASE_PRODUCT_URL/health" 200
check_endpoint "List Products" "$BASE_PRODUCT_URL/products" 200
check_endpoint "Get Product 1" "$BASE_PRODUCT_URL/products/1" 200
check_endpoint "Get Product 99 (Not Found)" "$BASE_PRODUCT_URL/products/99" 404

echo ""
echo "--- 3. Order Service (Port 8003) ---"
check_endpoint "Order Service Health" "$BASE_ORDER_URL/health" 200
check_endpoint "List Orders" "$BASE_ORDER_URL/orders" 200
check_endpoint "Get Order 1" "$BASE_ORDER_URL/orders/1" 200
check_endpoint "Get Order 99 (Not Found)" "$BASE_ORDER_URL/orders/99" 404

echo ""
echo "=========================================="
if [ "$FAILED" -eq 0 ]; then
    echo " RESULT: ALL SERVICES PASSED!"
    exit 0
else
    echo " RESULT: SOME CHECKS FAILED!"
    exit 1
fi

