import base64
import json
import sys
import time
import urllib.error
import urllib.request

COMMAND_API = "http://localhost:8001"
QUERY_API = "http://localhost:8002"
RABBITMQ_QUEUE = "http://localhost:15672/api/queues/%2F/product_events"
RABBITMQ_AUTH = base64.b64encode(b"guest:guest").decode()

passed = 0
failed = 0


def check(label: str, ok: bool) -> None:
    global passed, failed
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label}")
    if ok:
        passed += 1
    else:
        failed += 1


def http_json(url: str, method: str = "GET", payload: dict | None = None) -> dict | list | None:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=5) as resp:
        if resp.status == 204:
            return None
        return json.loads(resp.read())


def queue_depth() -> int:
    req = urllib.request.Request(RABBITMQ_QUEUE)
    req.add_header("Authorization", f"Basic {RABBITMQ_AUTH}")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read()).get("messages", 0)


def poll_until(condition, timeout: float = 10, interval: float = 0.3) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if condition():
            return True
        time.sleep(interval)
    return False


def write_products() -> list[dict]:
    return http_json(f"{COMMAND_API}/products")


def read_models() -> list[dict]:
    all_items: list[dict] = []
    offset = 0
    while offset < 10000:
        page = http_json(f"{QUERY_API}/products?limit=200&offset={offset}")
        all_items.extend(page)
        if len(page) < 200:
            break
        offset += 200
    return all_items


def main() -> None:
    print("== Validacao de sincronizacao PostgreSQL <-> RabbitMQ <-> Worker <-> Redis ==\n")

    products = [
        {"name": f"Sync Alpha {int(time.time())}", "price": 100.0, "stock": 5, "category": "Sync"},
        {"name": f"Sync Beta {int(time.time())}", "price": 250.0, "stock": 0, "category": "Sync"},
        {"name": f"Sync Gamma {int(time.time())}", "price": 1500.0, "stock": 8, "category": "Sync"},
    ]

    print("1) CRIAÇÃO (escrita -> evento -> projeção)")
    created_ids = []
    for p in products:
        resp = http_json(f"{COMMAND_API}/products", method="POST", payload=p)
        created_ids.append(resp["id"])
        print(f"  -> POST {p['name']}: id={resp['id']} (escrita confirmada)")

    check("RabbitMQ: fila drena (0 mensagens)", poll_until(lambda: queue_depth() == 0))
    check(
        "Worker: todos os produtos projetados no Redis",
        poll_until(lambda: all(any(r["id"] == i for r in read_models()) for i in created_ids)),
    )

    print("\n2) CONFORMIDADE: PostgreSQL (write) vs Redis (read)")
    for i, p in zip(created_ids, products):
        w = next(x for x in write_products() if x["id"] == i)
        r = next(x for x in read_models() if x["id"] == i)
        fields_ok = (
            w["name"] == r["name"]
            and w["price"] == r["price"]
            and w["category"] == r["category"]
        )
        derived_ok = r["in_stock"] == (w["stock"] > 0)
        check(f"produto {i}: campos iguais no write/read", fields_ok)
        check(f"produto {i}: in_stock derivado corretamente", derived_ok)

    print("\n3) ATUALIZAÇÃO (PUT -> ProductUpdated -> reprojeção)")
    target = created_ids[0]
    http_json(f"{COMMAND_API}/products/{target}", method="PUT", payload={"price": 88.0, "stock": 0})
    check(
        "RabbitMQ: fila drena (0 mensagens)",
        poll_until(lambda: queue_depth() == 0),
    )
    check(
        "Read Model atualizado (price 88.0, in_stock false)",
        poll_until(lambda: any(r["id"] == target and r["price"] == 88.0 and r["in_stock"] is False for r in read_models())),
    )

    print("\n4) REMOÇÃO (DELETE -> ProductDeleted -> HDEL)")
    target = created_ids[1]
    http_json(f"{COMMAND_API}/products/{target}", method="DELETE")
    check(
        "RabbitMQ: fila drena (0 mensagens)",
        poll_until(lambda: queue_depth() == 0),
    )
    check(
        "Read Model removeu o produto",
        poll_until(lambda: all(r["id"] != target for r in read_models())),
    )
    check(
        "PostgreSQL removeu o produto",
        all(w["id"] != target for w in write_products()),
    )

    print("\n5) LIMPEZA: produtos de teste criados")
    for i in created_ids:
        try:
            http_json(f"{COMMAND_API}/products/{i}", method="DELETE")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
    check(
        "Fila drena apos limpeza",
        poll_until(lambda: queue_depth() == 0),
    )

    print(f"\nRESULTADO: {passed} PASS, {failed} FAIL")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as e:
        print(f"ERRO de conexao (stack up?): {e}")
        sys.exit(1)
