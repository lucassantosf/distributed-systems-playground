"""
Script de Validação do Chat — Card 4.4

Valida o endpoint POST /chat (pipeline RAG completo: embedding da pergunta,
busca vetorial no pgvector, montagem do prompt e resposta do LLM):
  1. Obtém um repo_id já pronto (via argumento CLI, último repo 'ready' no banco
     ou submetendo o repositório padrão para ingestão)
  2. Faz 3 perguntas em sequência ao endpoint POST /chat
  3. Valida para cada resposta:
     - HTTP 200 OK
     - Campo `answer` não está vazio
     - Campo `sources` contém ao menos um arquivo
     - Registra a latência de cada chamada

Execução:
    docker compose exec api python scripts/validate_chat.py
    docker compose exec api python scripts/validate_chat.py <repo_id>
"""

import sys
import time

import httpx
from sqlalchemy import desc, func

from src.infrastructure.persistence.database import SessionLocal
from src.infrastructure.persistence.models import ChunkModel, RepositoryModel

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
# Helpers de output
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
# Obtenção do repositório pronto
# ==============================================================================

def resolve_ready_repo_id(cli_repo_id: str | None) -> str:
    """
    Retorna um repo_id com status 'ready' e chunks persistidos.
    Prioridade: argumento CLI -> último repo ready no banco -> nova ingestão.
    """
    step("1. Preparando repositório indexado...")

    if cli_repo_id:
        resp = httpx.get(f"{API_BASE_URL}/repos/{cli_repo_id}", timeout=10)
        if resp.status_code != 200:
            fail(f"GET /repos/{cli_repo_id} retornou {resp.status_code}: {resp.text}")
            sys.exit(1)
        data = resp.json()
        if data["status"] != "ready":
            fail(f"Repositório {cli_repo_id} não está pronto (status={data['status']})")
            sys.exit(1)
        ok(f"Usando repositório informado: {data['name']} ({cli_repo_id})")
        return cli_repo_id

    # Busca no banco o repositório mais recente já pronto com chunks
    db = SessionLocal()
    try:
        ready_repo = (
            db.query(RepositoryModel)
            .join(ChunkModel, ChunkModel.repository_id == RepositoryModel.id)
            .filter(RepositoryModel.status == "ready")
            .group_by(RepositoryModel.id)
            .having(func.count(ChunkModel.id) > 0)
            .order_by(desc(RepositoryModel.created_at))
            .first()
        )
        if ready_repo:
            repo_id = str(ready_repo.id)
            ok(f"Reaproveitando repositório pronto no banco: {ready_repo.name} ({repo_id})")
            return repo_id
    finally:
        db.close()

    # Nenhum pronto encontrado → submete e aguarda ingestão
    info(f"Nenhum repositório pronto encontrado. Submetendo {DEFAULT_REPO_URL}...")
    post_resp = httpx.post(
        f"{API_BASE_URL}/repos",
        json={"github_url": DEFAULT_REPO_URL},
        timeout=30,
    )
    if post_resp.status_code != 201:
        fail(f"POST /repos retornou {post_resp.status_code}: {post_resp.text}")
        sys.exit(1)

    repo_id = post_resp.json()["id"]
    info(f"Repositório submetido com id={repo_id}. Aguardando ingestão...")

    elapsed = 0
    while elapsed < POLL_TIMEOUT_SECONDS:
        get_resp = httpx.get(f"{API_BASE_URL}/repos/{repo_id}", timeout=10)
        status = get_resp.json()["status"]
        if status == "ready":
            ok(f"Ingestão concluída em ~{elapsed}s ({repo_id})")
            return repo_id
        if status == "error":
            fail("Ingestão terminou com status=error. Veja os logs do container api.")
            sys.exit(1)
        time.sleep(POLL_INTERVAL_SECONDS)
        elapsed += POLL_INTERVAL_SECONDS

    fail(f"Timeout de {POLL_TIMEOUT_SECONDS}s aguardando ingestão.")
    sys.exit(1)


# ==============================================================================
# Validação das perguntas no POST /chat
# ==============================================================================

def validate_chat_questions(repo_id: str) -> None:
    step("2. Executando 3 perguntas no endpoint POST /chat...")

    latencies_ms: list[float] = []

    for idx, question in enumerate(QUESTIONS, start=1):
        print(f"\n  [Pergunta {idx}/{len(QUESTIONS)}] {question}")

        start = time.perf_counter()
        response = httpx.post(
            f"{API_BASE_URL}/chat",
            json={"repo_id": repo_id, "question": question},
            timeout=CHAT_TIMEOUT_SECONDS,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        latencies_ms.append(latency_ms)

        if response.status_code != 200:
            fail(
                f"POST /chat retornou {response.status_code} "
                f"({latency_ms:.0f} ms): {response.text}"
            )
            sys.exit(1)

        data = response.json()
        answer = (data.get("answer") or "").strip()
        sources = data.get("sources") or []

        if not answer:
            fail(f"Resposta vazia recebida para a pergunta {idx}")
            sys.exit(1)

        if not isinstance(sources, list) or len(sources) == 0:
            fail(f"Campo 'sources' vazio para a pergunta {idx}")
            sys.exit(1)

        preview = answer.replace("\n", " ")
        if len(preview) > 140:
            preview = preview[:140] + "..."

        ok(f"Latência: {latency_ms:.0f} ms ({latency_ms / 1000:.2f}s)")
        ok(f"Sources ({len(sources)}): {', '.join(sources)}")
        info(f"Answer preview: {preview}")

    avg_ms = sum(latencies_ms) / len(latencies_ms)
    step("3. Resumo de Latência")
    for idx, ms in enumerate(latencies_ms, start=1):
        info(f"Pergunta {idx}: {ms:.0f} ms")
    ok(f"Latência média: {avg_ms:.0f} ms ({avg_ms / 1000:.2f}s)")


# ==============================================================================
# Main
# ==============================================================================

def main() -> None:
    cli_repo_id = sys.argv[1] if len(sys.argv) > 1 else None

    print("\n" + "=" * 60)
    print("  💬 Validação do Chat (RAG) — Card 4.4")
    print("=" * 60)
    info(f"API: {API_BASE_URL}")

    repo_id = resolve_ready_repo_id(cli_repo_id)
    validate_chat_questions(repo_id)

    print("\n" + "=" * 60)
    print("  🎉 Todas as validações do Chat passaram com sucesso!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
