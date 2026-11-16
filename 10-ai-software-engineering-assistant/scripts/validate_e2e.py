"""
Script de Validação End-to-End (E2E) — Card 6.1

Executa o fluxo completo da plataforma ponta-a-ponta:
  1. Submete a URL de um repositório público via POST /repos
  2. Aguarda a ingestão e indexação vetorial completar (status == 'ready')
  3. Faz 3 perguntas de negócio ao endpoint POST /chat
  4. Valida cada resposta (HTTP 200, answer não-vazio, sources >= 1)
  5. Imprime um relatório consolidado PASS/FAIL por etapa com métricas de latência

Execução:
    docker compose exec api python scripts/validate_e2e.py
    docker compose exec api python scripts/validate_e2e.py <github_url>

Exemplo:
    docker compose exec api python scripts/validate_e2e.py https://github.com/navdeep-G/samplemod
"""

import sys
import time
from dataclasses import dataclass
from typing import List, Optional

import httpx

# ==============================================================================
# Configuração
# ==============================================================================

API_BASE_URL = "http://localhost:8000"
DEFAULT_REPO_URL = "https://github.com/navdeep-G/samplemod"
POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 300
CHAT_TIMEOUT_SECONDS = 60

QUESTIONS = [
    "Qual é a estrutura principal e o propósito deste repositório?",
    "Quais funções ou módulos principais existem no código e o que eles fazem?",
    "Como o projeto é configurado ou testado?",
]


# ==============================================================================
# Modelos para o Relatório
# ==============================================================================

@dataclass
class StepResult:
    name: str
    passed: bool
    duration_seconds: float
    details: str
    error: Optional[str] = None


# ==============================================================================
# Helpers visuais
# ==============================================================================

def ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def fail(msg: str) -> None:
    print(f"  ❌ {msg}")


def info(msg: str) -> None:
    print(f"  ℹ️  {msg}")


def step(msg: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {msg}")
    print(f"{'─' * 60}")


# ==============================================================================
# Etapas do Fluxo E2E
# ==============================================================================

def step_submit_repository(client: httpx.Client, repo_url: str) -> tuple[Optional[str], StepResult]:
    """Etapa 1: Submete o repositório via POST /repos e extrai o ID."""
    step("Etapa 1: Submissão do Repositório (POST /repos)")
    info(f"Target: {repo_url}")

    start_time = time.perf_counter()
    try:
        response = client.post(
            f"{API_BASE_URL}/repos",
            json={"github_url": repo_url},
            timeout=30.0,
        )
        duration = time.perf_counter() - start_time

        if response.status_code != 201:
            err = f"Status code inesperado: {response.status_code} (esperado 201). Resposta: {response.text}"
            fail(err)
            return None, StepResult(
                name="1. Submissão do Repositório (POST /repos)",
                passed=False,
                duration_seconds=duration,
                details=f"HTTP {response.status_code}",
                error=err,
            )

        data = response.json()
        repo_id = data.get("id")
        initial_status = data.get("status")

        if not repo_id:
            err = f"Campo 'id' ausente no retorno: {data}"
            fail(err)
            return None, StepResult(
                name="1. Submissão do Repositório (POST /repos)",
                passed=False,
                duration_seconds=duration,
                details="Payload sem 'id'",
                error=err,
            )

        ok(f"Repositório registrado com sucesso! ID: {repo_id} | Status inicial: {initial_status} ({duration:.2f}s)")
        return repo_id, StepResult(
            name="1. Submissão do Repositório (POST /repos)",
            passed=True,
            duration_seconds=duration,
            details=f"ID={repo_id} | status={initial_status}",
        )

    except Exception as exc:
        duration = time.perf_counter() - start_time
        err = f"Exceção durante POST /repos: {exc}"
        fail(err)
        return None, StepResult(
            name="1. Submissão do Repositório (POST /repos)",
            passed=False,
            duration_seconds=duration,
            details="Erro de conexão/exceção",
            error=err,
        )


def step_wait_until_ready(client: httpx.Client, repo_id: str) -> StepResult:
    """Etapa 2: Realiza polling em GET /repos/{id} até status 'ready'."""
    step("Etapa 2: Ingestão e Indexação Vetorial (Polling GET /repos/{id})")
    info(f"Aguardando status 'ready' para o repositório {repo_id}...")

    start_time = time.perf_counter()
    elapsed = 0.0
    last_status = None

    while elapsed < POLL_TIMEOUT_SECONDS:
        try:
            resp = client.get(f"{API_BASE_URL}/repos/{repo_id}", timeout=10.0)
            if resp.status_code != 200:
                duration = time.perf_counter() - start_time
                err = f"GET /repos/{repo_id} falhou com status {resp.status_code}: {resp.text}"
                fail(err)
                return StepResult(
                    name="2. Ingestão e Indexação (GET /repos/{id})",
                    passed=False,
                    duration_seconds=duration,
                    details=f"Falha HTTP {resp.status_code}",
                    error=err,
                )

            data = resp.json()
            status_val = data.get("status")
            if status_val != last_status:
                info(f"Status atual: '{status_val}' (decorrido: {elapsed:.0f}s)")
                last_status = status_val

            if status_val == "ready":
                duration = time.perf_counter() - start_time
                ok(f"Repositório pronto para consultas em {duration:.1f}s!")
                return StepResult(
                    name="2. Ingestão e Indexação (GET /repos/{id})",
                    passed=True,
                    duration_seconds=duration,
                    details=f"Status final: ready em {duration:.1f}s",
                )

            if status_val == "failed":
                duration = time.perf_counter() - start_time
                err = f"Ingestão falhou no backend: {data.get('error_message') or 'Sem mensagem de erro'}"
                fail(err)
                return StepResult(
                    name="2. Ingestão e Indexação (GET /repos/{id})",
                    passed=False,
                    duration_seconds=duration,
                    details="Status: failed",
                    error=err,
                )

        except Exception as exc:
            info(f"Aviso de conexão durante polling: {exc}")

        time.sleep(POLL_INTERVAL_SECONDS)
        elapsed = time.perf_counter() - start_time

    duration = time.perf_counter() - start_time
    err = f"Timeout de {POLL_TIMEOUT_SECONDS}s excedido aguardando status 'ready'. Último status: '{last_status}'"
    fail(err)
    return StepResult(
        name="2. Ingestão e Indexação (GET /repos/{id})",
        passed=False,
        duration_seconds=duration,
        details="Timeout",
        error=err,
    )


def step_test_chat_question(
    client: httpx.Client,
    repo_id: str,
    question_idx: int,
    question: str,
) -> StepResult:
    """Etapa 3.x: Envia uma pergunta ao POST /chat e valida a resposta e as fontes."""
    step_name = f"3.{question_idx} Pergunta Chat: \"{question[:40]}...\""
    step(f"Etapa {step_name}")
    info(f"Pergunta completa: \"{question}\"")

    start_time = time.perf_counter()
    try:
        response = client.post(
            f"{API_BASE_URL}/chat",
            json={"repo_id": repo_id, "question": question},
            timeout=CHAT_TIMEOUT_SECONDS,
        )
        duration = time.perf_counter() - start_time

        if response.status_code != 200:
            err = f"POST /chat retornou HTTP {response.status_code}: {response.text}"
            fail(err)
            return StepResult(
                name=step_name,
                passed=False,
                duration_seconds=duration,
                details=f"HTTP {response.status_code}",
                error=err,
            )

        data = response.json()
        answer = data.get("answer", "")
        sources = data.get("sources", [])

        # Validação 1: answer não pode ser vazio
        if not isinstance(answer, str) or not answer.strip():
            err = "Campo 'answer' está vazio ou inválido na resposta."
            fail(err)
            return StepResult(
                name=step_name,
                passed=False,
                duration_seconds=duration,
                details="Resposta vazia",
                error=err,
            )

        # Validação 2: sources deve conter ao menos 1 arquivo
        if not isinstance(sources, list) or len(sources) == 0:
            err = f"Campo 'sources' deve conter ao menos 1 arquivo-fonte. Obtido: {sources}"
            fail(err)
            return StepResult(
                name=step_name,
                passed=False,
                duration_seconds=duration,
                details="Nenhuma fonte retornada",
                error=err,
            )

        ok(f"Resposta recebida em {duration:.2f}s com {len(sources)} fonte(s)")
        print(f"\n    📝 Resumo da resposta:\n    {answer.strip()[:180].replace(chr(10), ' ')}...")
        print(f"    📚 Fontes citadas: {', '.join(sources)}\n")

        return StepResult(
            name=step_name,
            passed=True,
            duration_seconds=duration,
            details=f"{len(sources)} fontes | latência: {duration:.2f}s",
        )

    except Exception as exc:
        duration = time.perf_counter() - start_time
        err = f"Exceção durante chamada POST /chat: {exc}"
        fail(err)
        return StepResult(
            name=step_name,
            passed=False,
            duration_seconds=duration,
            details="Erro de conexão/exceção",
            error=err,
        )


# ==============================================================================
# Relatório Final Consolidado
# ==============================================================================

def print_final_report(results: List[StepResult], total_elapsed: float) -> bool:
    print("\n" + "═" * 70)
    print("                RELATÓRIO DE VALIDAÇÃO END-TO-END (E2E)")
    print("═" * 70)
    print(f"{'Etapa':<48} {'Status':<10} {'Duração':<10}")
    print("─" * 70)

    all_passed = True
    chat_latencies: List[float] = []

    for res in results:
        status_tag = "✅ PASS" if res.passed else "❌ FAIL"
        if not res.passed:
            all_passed = False
        if res.name.startswith("3.") and res.passed:
            chat_latencies.append(res.duration_seconds)

        print(f"{res.name:<48} {status_tag:<10} {res.duration_seconds:6.2f}s")
        if res.error:
            print(f"   └─ Detalhe do erro: {res.error}")

    print("─" * 70)
    avg_chat = (sum(chat_latencies) / len(chat_latencies)) if chat_latencies else 0.0
    passed_count = sum(1 for r in results if r.passed)
    total_count = len(results)

    print(f"Total de etapas: {total_count} | Sucessos: {passed_count} | Falhas: {total_count - passed_count}")
    print(f"Tempo total de execução: {total_elapsed:.2f}s")
    if chat_latencies:
        print(f"Latência média do Chat:  {avg_chat:.2f}s")
    print("═" * 70)

    if all_passed:
        print("  🎉 FLUXO COMPLETO E2E EXECUTADO COM SUCESSO! [PASS]")
    else:
        print("  💥 FLUXO E2E APRESENTOU FALHAS! [FAIL]")
    print("═" * 70 + "\n")

    return all_passed


# ==============================================================================
# Main
# ==============================================================================

def main() -> None:
    repo_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REPO_URL

    print("\n" + "=" * 70)
    print("  🚀 INICIANDO TESTE END-TO-END (E2E) — CARD 6.1")
    print(f"  Repositório alvo: {repo_url}")
    print(f"  API Backend:      {API_BASE_URL}")
    print("=" * 70)

    overall_start = time.perf_counter()
    results: List[StepResult] = []

    with httpx.Client() as client:
        # Etapa 1: Submissão do repositório
        repo_id, step1_result = step_submit_repository(client, repo_url)
        results.append(step1_result)

        if not step1_result.passed or not repo_id:
            total_elapsed = time.perf_counter() - overall_start
            print_final_report(results, total_elapsed)
            sys.exit(1)

        # Etapa 2: Aguardar ingestão 'ready'
        step2_result = step_wait_until_ready(client, repo_id)
        results.append(step2_result)

        if not step2_result.passed:
            total_elapsed = time.perf_counter() - overall_start
            print_final_report(results, total_elapsed)
            sys.exit(1)

        # Etapa 3: 3 perguntas ao POST /chat
        for idx, question in enumerate(QUESTIONS, start=1):
            chat_result = step_test_chat_question(client, repo_id, idx, question)
            results.append(chat_result)

    total_elapsed = time.perf_counter() - overall_start
    success = print_final_report(results, total_elapsed)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
