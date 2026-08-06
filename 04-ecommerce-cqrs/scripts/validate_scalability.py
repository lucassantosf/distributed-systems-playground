import concurrent.futures
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

COMMAND_API = "http://localhost:8001"
QUERY_API_1 = "http://localhost:8002"
QUERY_API_2 = "http://localhost:8003"
RABBITMQ_QUEUE = "http://localhost:15672/api/queues/%2F/product_events"
RABBITMQ_AUTH = __import__("base64").b64encode(b"guest:guest").decode()

N_PRODUCTS = int(sys.argv[1]) if len(sys.argv) > 1 else 300
NETWORK = "04-ecommerce-cqrs_cqrs-net"
SECOND_INSTANCE = "cqrs_query_api_2"

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
    with urllib.request.urlopen(req, timeout=15) as resp:
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


def pg_stats() -> tuple[int, int]:
    out = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "cqrs", "-d", "command_db", "-t", "-A",
         "-c", "SELECT seq_scan, idx_scan FROM pg_stat_user_tables WHERE relname='products'"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    seq_scan, idx_scan = out.split("|")
    return int(seq_scan), int(idx_scan)


def read_one(base: str, product_id: int) -> dict:
    return http_json(f"{base}/products/{product_id}")


def read_page(base: str) -> list:
    return http_json(f"{base}/products?limit=200")


def run_phase_read_load(ids: list[int], duration: float = 4.0) -> dict:
    def worker(base: str, iterations: int) -> list[float]:
        latencies = []
        for i in range(iterations):
            if i % 5 == 0:
                t0 = time.perf_counter()
                read_one(base, ids[i % len(ids)])
            else:
                t0 = time.perf_counter()
                read_page(base)
            latencies.append((time.perf_counter() - t0) * 1000)
        return latencies

    t0 = time.monotonic()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [
            pool.submit(worker, base, 200)
            for base in (QUERY_API_1, QUERY_API_2)
            for _ in range(4)
        ]
        for f in concurrent.futures.as_completed(futures):
            results.extend(f.result())
    elapsed = time.monotonic() - t0
    results.sort()
    total_requests = len(results)
    avg = sum(results) / total_requests
    p95 = results[int(0.95 * (len(results) - 1))]
    return {"requests": total_requests, "throughput": total_requests / elapsed, "avg_ms": avg, "p95_ms": p95}


def main() -> None:
    print("== Validacao de escalabilidade: leitura e escrita independentes ==\n")

    print(f"1) SEMEANDO {N_PRODUCTS} produtos via Command API...")
    ids = []
    for i in range(N_PRODUCTS):
        ids.append(http_json(f"{COMMAND_API}/products", method="POST", payload={
            "name": f"Scale {i:04d}", "price": round(1.0 + (i % 300) * 1.5, 2), "stock": i % 7, "category": f"Cat{i % 10}",
        })["id"])
    check("fila drena", poll_until(lambda: queue_depth() == 0))
    check("projecao completa", poll_until(lambda: len(http_json(f"{QUERY_API_1}/products?limit=200")) > 0))

    print(f"\n2) SUBINDO 2a INSTANCIA DE LEITURA (:8003) apontando para o MESMO Redis...")
    subprocess.run(["docker", "rm", "-f", SECOND_INSTANCE], capture_output=True)
    base_dir = __import__("pathlib").Path(__file__).resolve().parents[1]
    subprocess.run([
        "docker", "run", "-d", "--name", SECOND_INSTANCE, "--network", NETWORK,
        "-p", "8003:8000",
        "-v", f"{base_dir}/query-api/app:/app", "-v", f"{base_dir}/:/workspace",
        "-e", "PYTHONPATH=/app:/workspace", "-e", "REDIS_URL=redis://redis:6379/0",
        "04-ecommerce-cqrs-query-api:latest",
    ], check=True, capture_output=True)
    check("2a instancia responde", poll_until(lambda: _health(QUERY_API_2), timeout=30))
    check(
        "ambas instancias leem os MESMOS dados do Redis",
        read_page(QUERY_API_1) == read_page(QUERY_API_2),
    )

    print("\n3) CARGA SO DE LEITURA nas 2 instancias - PostgreSQL deve ficar INTOCADO")
    commit_before, returned_before = pg_stats()
    r = run_phase_read_load(ids)
    commit_after, returned_after = pg_stats()
    print(f"   {r['requests']} leituras em {r['throughput']:.0f} req/s | media {r['avg_ms']:.1f}ms | p95 {r['p95_ms']:.1f}ms")
    print(f"   tabela products: seq_scan {commit_before} -> {commit_after} | idx_scan {returned_before} -> {returned_after}")
    check("nenhuma varredura sequencial na tabela products durante leituras", commit_after == commit_before)
    check("nenhuma leitura por indice na tabela products durante leituras", returned_after == returned_before)

    print("\n4) LEITURA + ESCRITA CONCORRENTES (independencia)")
    t0 = time.monotonic()

    def write_load(_: int) -> float:
        t0 = time.perf_counter()
        created = http_json(f"{COMMAND_API}/products", method="POST", payload={
            "name": f"Conc {int(time.time())}", "price": 5.0, "stock": 1, "category": "Conc",
        })
        http_json(f"{COMMAND_API}/products/{created['id']}", method="DELETE")
        return (time.perf_counter() - t0) * 1000

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        read_future = pool.submit(run_phase_read_load, ids)
        write_latencies = list(pool.map(write_load, range(30)))
    read_res = read_future.result()
    elapsed = time.monotonic() - t0
    write_avg = sum(write_latencies) / len(write_latencies)
    write_p95 = sorted(write_latencies)[int(0.95 * (len(write_latencies) - 1))]
    print(f"   leituras: {read_res['requests']} req ({read_res['throughput']:.0f} req/s, media {read_res['avg_ms']:.1f}ms)")
    print(f"   escritas: 30 POST+DELETE em {elapsed:.1f}s (media {write_avg:.1f}ms, p95 {write_p95:.1f}ms)")
    check("escritas completaram sem erro durante leituras", len(write_latencies) == 30)

    print("\n5) LIMPEZA")
    subprocess.run(["docker", "rm", "-f", SECOND_INSTANCE], capture_output=True)
    for i in ids:
        try:
            http_json(f"{COMMAND_API}/products/{i}", method="DELETE")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
    poll_until(lambda: queue_depth() == 0)
    print("   OK")

    print(f"\nRESULTADO: {passed} PASS, {failed} FAIL")
    sys.exit(1 if failed else 0)


def _health(base: str) -> bool:
    try:
        http_json(f"{base}/health")
        return True
    except Exception:
        return False


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as e:
        print(f"ERRO de conexao (stack up?): {e}")
        sys.exit(1)
