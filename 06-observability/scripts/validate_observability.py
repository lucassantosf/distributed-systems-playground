#!/usr/bin/env python3
"""
validate_observability.py — Validação E2E dos Três Pilares da Observabilidade
Card 16

Verifica de ponta a ponta:
  1. Faz uma requisição à sample-app injetando um `traceparent` W3C e verifica a resposta (201 Created).
  2. Consulta o Prometheus (Thanos) e verifica se a métrica `http_requests_total` foi registrada.
  3. Consulta a API do Tempo (`/api/traces/{trace_id}`) e verifica se o trace foi armazenado com seus Spans.
  4. Consulta o OpenSearch e verifica se existe um log estruturado contendo o mesmo `trace_id`.

Retorna PASS/FAIL para cada verificação e finaliza com código 0 (sucesso) ou 1 (falha).
"""
import json
import secrets
import sys
import time
import urllib.parse
import urllib.request


def print_status(check_name: str, passed: bool, detail: str = ""):
    symbol = "✅ PASS" if passed else "❌ FAIL"
    msg = f"[{symbol}] {check_name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def main():
    print("=" * 70)
    print("  VALIDAÇÃO E2E DA PLATAFORMA DE OBSERVABILIDADE (CARD 16)")
    print("=" * 70)
    print()

    # Gerar trace_id e span_id W3C aleatórios
    trace_id = secrets.token_hex(16)  # 32 hex chars
    span_id = secrets.token_hex(8)    # 16 hex chars
    traceparent = f"00-{trace_id}-{span_id}-01"

    all_passed = True

    # -------------------------------------------------------------------------
    # 1. Requisição com context propagation (traceparent)
    # -------------------------------------------------------------------------
    app_url = "http://localhost:8000/orders"
    payload = json.dumps({"item": "Validation Order Card 16"}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "traceparent": traceparent,
    }

    req = urllib.request.Request(app_url, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.status
            body = json.loads(resp.read().decode("utf-8"))
            order_id = body.get("id", "unknown")
            check1_pass = (status_code == 201)
            print_status(
                "1. Requisição à sample-app com W3C traceparent",
                check1_pass,
                f"HTTP {status_code} | order_id={order_id} | trace_id={trace_id}",
            )
            if not check1_pass:
                all_passed = False
    except Exception as e:
        print_status("1. Requisição à sample-app com W3C traceparent", False, str(e))
        all_passed = False
        sys.exit(1)

    # -------------------------------------------------------------------------
    # 2. Métricas no Prometheus (Thanos)
    # -------------------------------------------------------------------------
    # Prometheus faz scrape a cada 15s; aguardamos 5s para garantir atualização
    time.sleep(5)
    prom_query = urllib.parse.quote('sum(http_requests_total{job="sample-app"})')
    prom_url = f"http://localhost:9090/api/v1/query?query={prom_query}"

    try:
        with urllib.request.urlopen(prom_url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("data", {}).get("result", [])
            val = float(results[0]["value"][1]) if results else 0.0
            check2_pass = (val > 0)
            print_status(
                "2. Métrica http_requests_total no Prometheus",
                check2_pass,
                f"encontrada com total acumulado={int(val)} reqs",
            )
            if not check2_pass:
                all_passed = False
    except Exception as e:
        print_status("2. Métrica http_requests_total no Prometheus", False, str(e))
        all_passed = False

    # -------------------------------------------------------------------------
    # 3. Traces no Tempo
    # -------------------------------------------------------------------------
    tempo_url = f"http://localhost:3200/api/traces/{trace_id}"
    check3_pass = False
    detail3 = ""

    # OTel Collector e Tempo levam alguns segundos para processar e expor
    for attempt in range(10):
        try:
            with urllib.request.urlopen(tempo_url, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    batches = data.get("batches", [])
                    span_count = sum(len(b.get("scopeSpans", [])) for b in batches)
                    check3_pass = True
                    detail3 = f"Trace encontrado com {span_count} grupo(s) de spans"
                    break
        except Exception:
            time.sleep(1.5)

    if not check3_pass:
        detail3 = f"Trace {trace_id} não encontrado após 15s"

    print_status("3. Trace no Grafana Tempo", check3_pass, detail3)
    if not check3_pass:
        all_passed = False

    # -------------------------------------------------------------------------
    # 4. Logs no OpenSearch (Filebeat -> Logstash -> OpenSearch)
    # -------------------------------------------------------------------------
    opensearch_url = "http://localhost:9200/observability-logs-*/_search"
    search_payload = json.dumps({
        "query": {
            "match": {
                "trace_id": trace_id
            }
        }
    }).encode("utf-8")

    check4_pass = False
    detail4 = ""

    # Aguardar pipeline Filebeat -> Logstash -> OpenSearch (flush interval ~5s)
    for attempt in range(12):
        try:
            req_os = urllib.request.Request(
                opensearch_url, data=search_payload, headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(req_os, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    total_hits = data.get("hits", {}).get("total", {}).get("value", 0)
                    if total_hits > 0:
                        check4_pass = True
                        log_msg = data["hits"]["hits"][0]["_source"].get("message", "")[:50]
                        detail4 = f"{total_hits} log(s) encontrado(s) | Exemplo: '{log_msg}...'"
                        break
        except Exception:
            pass
        time.sleep(2)

    if not check4_pass:
        detail4 = f"Nenhum log com trace_id={trace_id} encontrado no OpenSearch após 24s"

    print_status("4. Log estruturado no OpenSearch", check4_pass, detail4)
    if not check4_pass:
        all_passed = False

    print()
    print("=" * 70)
    if all_passed:
        print("  RESULTADO: TODOS OS CHECKS PASSARAM! OBSERVABILIDADE 100% OK ✅")
        print("=" * 70)
        sys.exit(0)
    else:
        print("  RESULTADO: FALHA EM UM OU MAIS CHECKS ❌")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
