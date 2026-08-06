import json
import sys
import time
import urllib.error
import urllib.request

COMMAND_API = "http://localhost:8001"
QUERY_API = "http://localhost:8002"
RABBITMQ_QUEUE = "http://localhost:15672/api/queues/%2F/product_events"
RABBITMQ_DLQ = "http://localhost:15672/api/queues/%2F/product_events.dlq"
RABBITMQ_AUTH = __import__("base64").b64encode(b"guest:guest").decode()

passed = 0
failed = 0


def check(label: str, ok: bool) -> None:
    global passed, failed
    print(f"  [{('PASS' if ok else 'FAIL')}] {label}")
    passed += ok
    failed += not ok


def http_json(url: str, method: str = "GET", payload: dict | None = None) -> dict | list | None:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status == 204:
            return None
        return json.loads(resp.read())


def queue_info() -> dict:
    req = urllib.request.Request(RABBITMQ_QUEUE)
    req.add_header("Authorization", f"Basic {RABBITMQ_AUTH}")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def poll_until(condition, timeout: float = 15, interval: float = 0.3) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if condition():
            return True
        time.sleep(interval)
    return False


def main() -> None:
    print("== Fluxo completo: Command -> Evento -> Projection -> Query ==\n")

    print("1) ESCREVER (Command API -> PostgreSQL)")
    payload = {"name": "Fluxo Completo", "price": 1299.90, "stock": 4, "category": "Final"}
    created = http_json(f"{COMMAND_API}/products", method="POST", payload=payload)
    product_id = created["id"]
    print(f"   POST /products -> 201, id={product_id} (persistido no PostgreSQL)")
    write = next(p for p in http_json(f"{COMMAND_API}/products") if p["id"] == product_id)
    check("produto persistido no banco de escrita", write["name"] == "Fluxo Completo")

    print("\n2) PUBLICAR (Command API -> RabbitMQ)")
    check("fila recebeu o evento e drena", poll_until(lambda: queue_info()["messages"] == 0))

    print("\n3) PROJETAR (Worker -> Redis)")
    check(
        "Read Model no Redis com campos derivados",
        poll_until(lambda: any(
            r["id"] == product_id and r["in_stock"] is True and r["price_tier"] == "high"
            and r["formatted_price"] == "R$ 1.299,90" and r["name_normalized"] == "fluxo completo"
            for r in http_json(f"{QUERY_API}/products?q=fluxo")
        )),
    )

    print("\n4) LER (Query API -> Redis, sem tocar o PostgreSQL)")
    read = http_json(f"{QUERY_API}/products/{product_id}")
    print(f"   GET /products/{product_id} -> {json.dumps(read, ensure_ascii=False)}")
    check("leitura pontual do Read Model", read["name"] == "Fluxo Completo" and read["price"] == 1299.9)

    print("\n5) ATUALIZAR (PUT -> ProductUpdated -> reprojecao)")
    http_json(f"{COMMAND_API}/products/{product_id}", method="PUT", payload={"price": 99.9, "stock": 0})
    check(
        "reprojetado com novos valores",
        poll_until(lambda: any(
            r["id"] == product_id and r["price"] == 99.9 and r["in_stock"] is False
            and r["price_tier"] == "low" and r["formatted_price"] == "R$ 99,90"
            for r in http_json(f"{QUERY_API}/products?q=fluxo")
        )),
    )

    print("\n6) REMOVER (DELETE -> ProductDeleted -> HDEL)")
    http_json(f"{COMMAND_API}/products/{product_id}", method="DELETE")
    check(
        "sumiu do Read Model",
        poll_until(lambda: any(
            r["id"] == product_id for r in http_json(f"{QUERY_API}/products?q=fluxo&limit=200")
        ) is False),
    )
    try:
        http_json(f"{QUERY_API}/products/{product_id}")
        removed = False
    except urllib.error.HTTPError as e:
        removed = e.code == 404
    check("Query API responde 404 apos remocao", removed)

    print(f"\nRESULTADO: {passed} PASS, {failed} FAIL")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as e:
        print(f"ERRO de conexao (stack up?): {e}")
        sys.exit(1)
