import json
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request

COMMAND_API = "http://localhost:8001"
QUERY_API = "http://localhost:8002"
RABBITMQ_QUEUE = "http://localhost:15672/api/queues/%2F/product_events"
RABBITMQ_AUTH = __import__("base64").b64encode(b"guest:guest").decode()

N_PRODUCTS = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
STORAGE_ITER = 30
API_ITER = 50
API_WARMUP = 5
PAGE_SIZE = 200


def http_json(url: str, method: str = "GET", payload: dict | None = None) -> dict | list | None:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        if resp.status == 204:
            return None
        return json.loads(resp.read())


def queue_depth() -> int:
    req = urllib.request.Request(RABBITMQ_QUEUE)
    req.add_header("Authorization", f"Basic {RABBITMQ_AUTH}")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read()).get("messages", 0)


def poll_until(condition, timeout: float = 90, interval: float = 0.3) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if condition():
            return True
        time.sleep(interval)
    return False


def bench_http(label: str, url: str, iterations: int = API_ITER) -> tuple[float, float, float]:
    for _ in range(API_WARMUP):
        http_json(url)
    samples = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        http_json(url)
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    return statistics.mean(samples), samples[0], samples[int(0.95 * (len(samples) - 1))]


def bench_storage(label: str, container: str, sql: str, iterations: int = STORAGE_ITER) -> tuple[float, float, float]:
    t0 = time.perf_counter()
    subprocess.run(["docker", "compose", "exec", "-T", container, "sh", "-c", sql], check=True, capture_output=True)
    per_iter_ms = ((time.perf_counter() - t0) / iterations) * 1000
    return per_iter_ms, per_iter_ms, per_iter_ms


def main() -> None:
    print(f"== Benchmark de consultas: PostgreSQL (write DB) vs Redis (read model) ==\n")
    print(f"Dados: {N_PRODUCTS} produtos\n")

    print(f"1) SEMEANDO {N_PRODUCTS} produtos via Command API...")
    ids = []
    for i in range(N_PRODUCTS):
        ids.append(http_json(f"{COMMAND_API}/products", method="POST", payload={
            "name": f"Bench {i:04d}", "price": round(1.0 + (i % 500) * 1.5, 2), "stock": i % 7, "category": f"Cat{i % 10}",
        })["id"])
    if not poll_until(lambda: queue_depth() == 0):
        print("ERRO: fila nao drenou")
        sys.exit(1)
    total = 0
    for off in range(0, N_PRODUCTS, PAGE_SIZE):
        total += len(http_json(f"{QUERY_API}/products?limit={PAGE_SIZE}&offset={off}"))
    if total != N_PRODUCTS:
        print(f"ERRO: projecao incompleta ({total}/{N_PRODUCTS})")
        sys.exit(1)
    print(f"   Escritos no PostgreSQL e projetados no Redis: {N_PRODUCTS} ok\n")

    print(f"2) NIVEL DE ARMAZENAMENTO (psql vs redis-cli, {STORAGE_ITER} iters/bloco, ms por iteracao)")
    pg_sql = f"for i in $(seq 1 {STORAGE_ITER}); do psql -U cqrs -d command_db -t -A -c \"SELECT id, name, price, stock, category FROM products ORDER BY id\" >/dev/null; done"
    rd_sql = f"for i in $(seq 1 {STORAGE_ITER}); do redis-cli HGETALL products >/dev/null; done"
    pg_one = f"for i in $(seq 1 {STORAGE_ITER}); do psql -U cqrs -d command_db -t -A -c \"SELECT id, name, price, stock, category FROM products WHERE id={ids[0]}\" >/dev/null; done"
    rd_one = f"for i in $(seq 1 {STORAGE_ITER}); do redis-cli HGET products {ids[0]} >/dev/null; done"

    pg_all, pg_all_min, pg_all_p95 = bench_storage("PG", "postgres", pg_sql)
    rd_all, rd_all_min, rd_all_p95 = bench_storage("Redis", "redis", rd_sql)
    pg_one, _, _ = bench_storage("PG", "postgres", pg_one)
    rd_one, _, _ = bench_storage("Redis", "redis", rd_one)

    print(f"{'consulta':<28} {'media':>8} {'min':>8} {'p95':>8}")
    print(f"{'PG SELECT * (todos)':<28} {pg_all:>8.2f} {pg_all_min:>8.2f} {pg_all_p95:>8.2f}")
    print(f"{'Redis HGETALL (todos)':<28} {rd_all:>8.2f} {rd_all_min:>8.2f} {rd_all_p95:>8.2f}")
    print(f"{'PG SELECT WHERE id':<28} {pg_one:>8.2f}")
    print(f"{'Redis HGET <id>':<28} {rd_one:>8.2f}")
    print(f"\nGanho no armazenamento (todos): {pg_all / rd_all:.1f}x  |  (um registro): {pg_one / rd_one:.1f}x\n")

    print(f"3) NIVEL DE API (HTTP + JSON, {API_ITER} medicoes, ms por chamada)")
    print(f"   * PG: 1x GET :8001/products (retorna todos os {N_PRODUCTS})")
    print(f"   * Redis: paginado limit={PAGE_SIZE} -> { -(-N_PRODUCTS // PAGE_SIZE) }x GET :8002/products")

    pg_mean, pg_min, pg_p95 = bench_http("PG list", f"{COMMAND_API}/products")
    rd_times = []
    for off in range(0, N_PRODUCTS, PAGE_SIZE):
        t0 = time.perf_counter()
        http_json(f"{QUERY_API}/products?limit={PAGE_SIZE}&offset={off}")
        rd_times.append((time.perf_counter() - t0) * 1000)
    rd_total = sum(rd_times)
    rd_get_mean, rd_get_min, rd_get_p95 = bench_http("Redis get", f"{QUERY_API}/products/{ids[0]}")

    print(f"{'consulta':<28} {'media':>8} {'min':>8} {'p95':>8}")
    print(f"{'PG list (1 chamada)':<28} {pg_mean:>8.2f} {pg_min:>8.2f} {pg_p95:>8.2f}")
    print(f"{'Redis list total':<28} {rd_total:>8.2f}")
    print(f"{'Redis get (1 chamada)':<28} {rd_get_mean:>8.2f} {rd_get_min:>8.2f} {rd_get_p95:>8.2f}")
    print(f"\nGanho no nivel de API: PG {pg_mean:.2f}ms vs Redis total {rd_total:.2f}ms -> {pg_mean / rd_total:.1f}x")

    print("\n4) LIMPEZA: removendo produtos de teste")
    for i in ids:
        try:
            http_json(f"{COMMAND_API}/products/{i}", method="DELETE")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
    poll_until(lambda: queue_depth() == 0)
    print("   OK")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as e:
        print(f"ERRO de conexao (stack up?): {e}")
        sys.exit(1)
