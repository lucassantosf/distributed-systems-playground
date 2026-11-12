"""
Script de Validação da Ingestão — Card 3.6

Valida o pipeline completo de ingestão ponta a ponta:
  1. Submete um repositório público pequeno via POST /repos
  2. Faz polling em GET /repos/{id} até status=ready ou timeout
  3. Consulta a tabela chunks diretamente no banco e verifica:
     - Existem chunks para o repositório
     - Os embeddings têm a dimensão esperada (1536 para text-embedding-3-small)

Execução:
    docker compose exec api python scripts/validate_ingestion.py
    docker compose exec api python scripts/validate_ingestion.py <github_url>

Exemplo:
    docker compose exec api python scripts/validate_ingestion.py https://github.com/navdeep-G/samplemod
"""

import sys
import time

import httpx
from sqlalchemy import func, text

from src.infrastructure.persistence.database import SessionLocal
from src.infrastructure.persistence.models import ChunkModel, RepositoryModel
from src.settings import settings

# ==============================================================================
# Configuração
# ==============================================================================

API_BASE_URL = "http://localhost:8000"
DEFAULT_REPO_URL = "https://github.com/navdeep-G/samplemod"
POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 300  # 5 minutos (repos maiores podem demorar)
EXPECTED_EMBEDDING_DIM = 1536  # text-embedding-3-small


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
# Validações
# ==============================================================================

def submit_repository(github_url: str) -> str:
    """Submete o repositório para ingestão e retorna o repo_id."""
    step("1. Submetendo repositório para ingestão...")
    info(f"URL: {github_url}")

    response = httpx.post(
        f"{API_BASE_URL}/repos",
        json={"github_url": github_url},
        timeout=30,
    )

    if response.status_code != 201:
        fail(f"POST /repos retornou {response.status_code}: {response.text}")
        sys.exit(1)

    data = response.json()
    repo_id = data["id"]
    ok(f"Repositório criado com id={repo_id}, status={data['status']}")
    return repo_id


def poll_until_ready(repo_id: str) -> dict:
    """Faz polling em GET /repos/{id} até status=ready ou timeout."""
    step("2. Aguardando ingestão ficar pronta...")

    elapsed = 0
    last_status = None

    while elapsed < POLL_TIMEOUT_SECONDS:
        response = httpx.get(f"{API_BASE_URL}/repos/{repo_id}", timeout=10)

        if response.status_code != 200:
            fail(f"GET /repos/{repo_id} retornou {response.status_code}: {response.text}")
            sys.exit(1)

        data = response.json()
        status = data["status"]

        if status != last_status:
            info(f"Status: {status} (elapsed: {elapsed}s)")
            last_status = status

        if status == "ready":
            ok(f"Ingestão concluída em ~{elapsed}s")
            return data

        if status == "error":
            fail("Ingestão terminou com status=error. Veja os logs do container api.")
            sys.exit(1)

        time.sleep(POLL_INTERVAL_SECONDS)
        elapsed += POLL_INTERVAL_SECONDS

    fail(f"Timeout de {POLL_TIMEOUT_SECONDS}s atingido. Status atual: {last_status}")
    sys.exit(1)


def validate_chunks_in_db(repo_id: str) -> None:
    """Consulta o banco e valida existência e dimensão dos embeddings."""
    step("3. Validando chunks e embeddings no banco...")

    db = SessionLocal()
    try:
        # 3a. Verifica que o repo existe no banco
        repo_model = db.query(RepositoryModel).filter(
            RepositoryModel.id == repo_id
        ).first()

        if not repo_model:
            fail(f"Repositório {repo_id} não encontrado na tabela repositories")
            sys.exit(1)
        ok(f"Repositório encontrado: name={repo_model.name}, status={repo_model.status}")

        # 3b. Conta chunks persistidos
        total_chunks = db.query(func.count(ChunkModel.id)).filter(
            ChunkModel.repository_id == repo_id
        ).scalar()

        if total_chunks == 0:
            fail("Nenhum chunk encontrado na tabela chunks para este repositório")
            sys.exit(1)
        ok(f"Total de chunks persistidos: {total_chunks}")

        # 3c. Conta chunks com embedding gerado
        chunks_with_embedding = db.query(func.count(ChunkModel.id)).filter(
            ChunkModel.repository_id == repo_id,
            ChunkModel.embedding.isnot(None),
        ).scalar()

        if chunks_with_embedding == 0:
            fail("Nenhum chunk possui embedding gerado")
            sys.exit(1)
        ok(f"Chunks com embedding: {chunks_with_embedding}/{total_chunks}")

        # 3d. Verifica dimensão do embedding em um chunk de amostra
        sample = db.query(ChunkModel).filter(
            ChunkModel.repository_id == repo_id,
            ChunkModel.embedding.isnot(None),
        ).first()

        if sample and sample.embedding is not None:
            dim = len(sample.embedding)
            if dim == EXPECTED_EMBEDDING_DIM:
                ok(f"Dimensão do embedding: {dim} (esperado: {EXPECTED_EMBEDDING_DIM}) ✓")
            else:
                fail(
                    f"Dimensão do embedding incorreta: {dim} "
                    f"(esperado: {EXPECTED_EMBEDDING_DIM})"
                )
                sys.exit(1)
        else:
            fail("Não foi possível obter sample de embedding para validar dimensão")
            sys.exit(1)

        # 3e. Exibe distribuição de chunks por arquivo (top 5)
        rows = db.execute(
            text(
                """
                SELECT file_path, COUNT(*) as n
                FROM chunks
                WHERE repository_id = :repo_id
                GROUP BY file_path
                ORDER BY n DESC
                LIMIT 5
                """
            ),
            {"repo_id": repo_id},
        ).fetchall()

        info("Top 5 arquivos por número de chunks:")
        for row in rows:
            print(f"       {row.n:>4}x  {row.file_path}")

    finally:
        db.close()


# ==============================================================================
# Main
# ==============================================================================

def main() -> None:
    github_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REPO_URL

    print("\n" + "=" * 60)
    print("  🔍 Validação da Ingestão — Card 3.6")
    print("=" * 60)
    info(f"API: {API_BASE_URL}")
    info(f"Repositório alvo: {github_url}")
    info(f"Modelo de embedding esperado: {settings.embedding_model} ({EXPECTED_EMBEDDING_DIM}d)")

    repo_id = submit_repository(github_url)
    poll_until_ready(repo_id)
    validate_chunks_in_db(repo_id)

    print("\n" + "=" * 60)
    print("  🎉 Todas as validações passaram com sucesso!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
