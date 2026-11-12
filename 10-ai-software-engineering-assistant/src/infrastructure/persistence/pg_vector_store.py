"""
PgVectorStore — Card 3.4

Implementação concreta de VectorStore que persiste e busca CodeChunks
usando PostgreSQL com a extensão pgvector.

Responsabilidades:
  - save_chunks: bulk insert de chunks com seus embeddings na tabela `chunks`
  - search: busca por similaridade coseno via operador `<=>` do pgvector,
            filtrada por repositório e limitada a top_k resultados

Regras de Clean Architecture:
  - Apenas esta classe conhece ChunkModel e SQLAlchemy
  - Retorna entidades de domínio (CodeChunk), nunca modelos SQLAlchemy
  - Use Cases dependem apenas da interface VectorStore
"""

import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.application.interfaces.vector_store import VectorStore
from src.domain.entities.code_chunk import CodeChunk
from src.infrastructure.persistence.models import ChunkModel

logger = logging.getLogger(__name__)


class PgVectorStore(VectorStore):
    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Contrato público (VectorStore)
    # ------------------------------------------------------------------

    def save_chunks(self, chunks: list[CodeChunk]) -> None:
        """
        Persiste uma lista de CodeChunk com seus embeddings no banco.

        Usa bulk insert via add_all para minimizar round-trips ao banco.
        Chunks sem embedding (embedding=None) são aceitos — a coluna é nullable.

        Args:
            chunks: Lista de CodeChunk já processados (embedding pode ser None
                    se o EmbeddingProvider ainda não estiver configurado).
        """
        if not chunks:
            logger.debug("save_chunks chamado com lista vazia — nada a persistir")
            return

        models = [
            ChunkModel(
                id=chunk.id,
                repository_id=chunk.repository_id,
                file_path=chunk.file_path,
                content=chunk.content,
                embedding=chunk.embedding,
                chunk_index=chunk.chunk_index,
            )
            for chunk in chunks
        ]

        self._db.add_all(models)
        self._db.commit()

        logger.info(
            "Persistidos %d chunk(s) para o repositório %s",
            len(chunks),
            chunks[0].repository_id,
        )

    def search(
        self,
        embedding: list[float],
        repo_id: UUID,
        top_k: int,
    ) -> list[CodeChunk]:
        """
        Busca os `top_k` chunks mais similares ao vetor `embedding`,
        filtrando pelo repositório `repo_id`.

        Usa o operador de distância coseno `<=>` do pgvector.
        Quanto menor a distância, maior a similaridade semântica.

        Args:
            embedding: Vetor da query do usuário gerado pelo EmbeddingProvider.
            repo_id:   Restringe a busca aos chunks deste repositório.
            top_k:     Número máximo de resultados a retornar.

        Returns:
            Lista de CodeChunk ordenada por similaridade (mais próximo primeiro).
        """
        # Converte o vetor Python para a string no formato aceito pelo pgvector: '[f1,f2,...]'
        embedding_literal = "[" + ",".join(str(v) for v in embedding) + "]"

        rows = (
            self._db.query(ChunkModel)
            .filter(ChunkModel.repository_id == repo_id)
            .filter(ChunkModel.embedding.isnot(None))
            .order_by(
                # Distância coseno: `<=>` — menor = mais similar
                text(f"embedding <=> '{embedding_literal}'")
            )
            .limit(top_k)
            .all()
        )

        logger.debug(
            "Busca vetorial retornou %d resultado(s) para repo %s (top_k=%d)",
            len(rows),
            repo_id,
            top_k,
        )

        return [self._to_entity(row) for row in rows]

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    @staticmethod
    def _to_entity(model: ChunkModel) -> CodeChunk:
        """Converte um ChunkModel SQLAlchemy para a entidade de domínio CodeChunk."""
        return CodeChunk(
            id=model.id,
            repository_id=model.repository_id,
            file_path=model.file_path,
            content=model.content,
            chunk_index=model.chunk_index,
            embedding=list(model.embedding) if model.embedding is not None else None,
        )
