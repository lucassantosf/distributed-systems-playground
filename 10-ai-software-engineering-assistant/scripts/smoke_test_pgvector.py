"""
Smoke test: valida que o pgvector está funcionando corretamente.

O que este script testa:
1. Conexão com o PostgreSQL
2. Extensão vector habilitada
3. Inserção de chunks com embeddings fictícios
4. Busca por similaridade com o operador <=>
5. O chunk mais próximo é retornado corretamente

Executar dentro do container:
    docker compose exec api python scripts/smoke_test_pgvector.py

Ou localmente (com DATABASE_URL apontando para o banco):
    python scripts/smoke_test_pgvector.py
"""

import uuid

from sqlalchemy import text

from src.infrastructure.persistence.database import SessionLocal, engine
from src.infrastructure.persistence.models import Base, ChunkModel, RepositoryModel


def run() -> None:
    print("=== Smoke Test: pgvector ===\n")

    # --- Setup: garantir tabelas existem (só para o smoke test standalone) ---
    # Em produção as tabelas são criadas via Alembic.
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        # 1. Verificar extensão
        result = db.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
        row = result.fetchone()
        assert row is not None, "FAIL: extensão 'vector' não está instalada"
        print(f"[OK] Extensão pgvector instalada: {row[0]}")

        # 2. Criar um repositório fictício
        repo = RepositoryModel(
            id=uuid.uuid4(),
            github_url="https://github.com/smoke/test",
            name="smoke-test",
            status="ready",
        )
        db.add(repo)
        db.flush()

        # 3. Inserir dois chunks com embeddings sintéticos
        # chunk_a: vetor "apontando" na direção [1, 0, 0, ...]
        # chunk_b: vetor "apontando" na direção oposta [0, 1, 0, ...]
        dim = 1536
        chunk_a = ChunkModel(
            id=uuid.uuid4(),
            repository_id=repo.id,
            file_path="src/auth.py",
            content="def authenticate(user, password): ...",
            embedding=[1.0] + [0.0] * (dim - 1),
            chunk_index=0,
        )
        chunk_b = ChunkModel(
            id=uuid.uuid4(),
            repository_id=repo.id,
            file_path="src/models.py",
            content="class User(BaseModel): ...",
            embedding=[0.0] * (dim - 1) + [1.0],
            chunk_index=0,
        )
        db.add_all([chunk_a, chunk_b])
        db.flush()

        # 4. Busca por similaridade — query próxima do chunk_a
        query_embedding = [1.0] + [0.0] * (dim - 1)
        query_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        result = db.execute(
            text(
                "SELECT file_path, embedding <=> :q AS distance "
                "FROM chunks "
                "WHERE repository_id = :repo_id "
                "ORDER BY distance "
                "LIMIT 1"
            ),
            {"q": query_str, "repo_id": str(repo.id)},
        )
        top = result.fetchone()

        assert top is not None, "FAIL: nenhum chunk retornado"
        assert top[0] == "src/auth.py", (
            f"FAIL: esperado 'src/auth.py', recebido '{top[0]}'"
        )
        print(f"[OK] Busca por similaridade retornou o chunk correto: {top[0]} (distance={top[1]:.4f})")

        # 5. Rollback — não deixar lixo no banco
        db.rollback()
        print("\n[OK] Rollback realizado — nenhum dado persistido")

    print("\n=== RESULTADO: PASS ===")


if __name__ == "__main__":
    run()

