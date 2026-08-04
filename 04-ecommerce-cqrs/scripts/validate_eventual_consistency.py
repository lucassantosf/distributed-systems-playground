import json
import time
import urllib.request

COMMAND_API = "http://localhost:8001"
QUERY_API = "http://localhost:8002"
TIMEOUT_S = 15


def post_product(name: str) -> dict:
    payload = json.dumps({
        "name": name,
        "price": 99.9,
        "stock": 5,
        "category": "Consistencia",
    }).encode()
    req = urllib.request.Request(
        f"{COMMAND_API}/products",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def list_products() -> list[dict]:
    with urllib.request.urlopen(f"{QUERY_API}/products", timeout=5) as resp:
        return json.loads(resp.read())


def is_visible(product_id: int) -> bool:
    return any(p["id"] == product_id for p in list_products())


def main() -> None:
    name = f"Consistencia Eventual {int(time.time())}"

    t0 = time.monotonic()
    product = post_product(name)
    t_write = (time.monotonic() - t0) * 1000
    print(f"[1] Escrita no Command API: id={product['id']} ({name}) em {t_write:.1f} ms")

    t1 = time.monotonic()
    immediately = is_visible(product["id"])
    print(f"[2] Consulta IMEDIATA no Query API: visivel? {immediately}")

    t2 = time.monotonic()
    while not is_visible(product["id"]):
        if time.monotonic() - t2 > TIMEOUT_S:
            print("[3] TIMEOUT: produto nao apareceu no Read Model.")
            return
        time.sleep(0.2)
    t_visible = (time.monotonic() - t2) * 1000

    print(f"[3] Produto visivel no Read Model apos {t_visible:.0f} ms")
    print()
    print("Resumo:")
    print(f"  Escrita confirmada em {t_write:.1f} ms (Command API)")
    print(f"  Janela de consistencia eventual: {t_visible:.0f} ms")
    if t_visible > 100:
        print("  -> A leitura logo apos a escrita NAO refletiu a mudanca: consistencia eventual observada.")
    else:
        print("  -> Leitura quase imediata: a janela natural e pequena demais para notar.")


if __name__ == "__main__":
    main()
