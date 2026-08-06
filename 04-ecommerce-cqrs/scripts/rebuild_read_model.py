import argparse
import json
import sys
import time
import urllib.error
import urllib.request

COMMAND_API = "http://command-api:8000"
QUEUE = "http://rabbitmq:15672/api/queues/%2F/product_events"
AUTH = __import__("base64").b64encode(b"guest:guest").decode()

TEST_PREFIXES = ("Sync", "Consistencia", "Conc", "Bench", "Scale", "Teste Validacao")


def http_json(url: str, method: str = "GET", payload: dict | None = None) -> dict | list | None:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status == 204:
            return None
        return json.loads(resp.read())


def queue_depth() -> int:
    req = urllib.request.Request(QUEUE)
    req.add_header("Authorization", f"Basic {AUTH}")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read()).get("messages", 0)


def poll_until(condition, timeout: float = 30, interval: float = 0.3) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if condition():
            return True
        time.sleep(interval)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconstroi o Read Model no Redis a partir do PostgreSQL.")
    parser.add_argument("--clean-test", action="store_true", help="remove antes os produtos de teste do PostgreSQL")
    args = parser.parse_args()

    from config import settings
    import redis as redis_lib
    from projection import build_read_model

    r = redis_lib.from_url(settings.redis_url)

    products = http_json(f"{COMMAND_API}/products")
    print(f"PostgreSQL: {len(products)} produtos (fonte de verdade)")

    if args.clean_test:
        junk = [p for p in products if p["name"].startswith(TEST_PREFIXES)]
        print(f"Removendo {len(junk)} produtos de teste residuais...")
        for p in junk:
            http_json(f"{COMMAND_API}/products/{p['id']}", method="DELETE")
        poll_until(lambda: queue_depth() == 0)
        products = http_json(f"{COMMAND_API}/products")
        print(f"PostgreSQL apos limpeza: {len(products)} produtos")

    print("Purgando Read Model atual no Redis...")
    r.delete("products")

    rebuilt = 0
    for p in products:
        event = {
            "event": "ProductCreated",
            "product_id": p["id"],
            "name": p["name"],
            "price": float(p["price"]),
            "stock": p["stock"],
            "category": p["category"],
        }
        read_model = build_read_model(event)
        r.hset("products", read_model.id, read_model.model_dump_json())
        rebuilt += 1

    actual = r.hlen("products")
    print(f"Read Model reconstruido no Redis: {rebuilt} produtos (hash total: {actual})")

    if actual != len(products):
        print("ERRO: Redis e PostgreSQL divergem apos a reconstrucao")
        sys.exit(1)
    print("Consistencia restaurada: Redis == PostgreSQL")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as e:
        print(f"ERRO de conexao (rode de dentro do container projection-worker): {e}")
        sys.exit(1)
