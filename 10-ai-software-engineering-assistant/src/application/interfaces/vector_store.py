"""
Contrato: VectorStore

Define como qualquer banco vetorial deve se comportar para persistir e buscar chunks.
O Use Case depende desta abstração — nunca do PostgreSQL/pgvector diretamente.

Implementação concreta: infrastructure/persistence/pg_vector_store.py
"""

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.code_chunk import CodeChunk


class VectorStore(ABC):
    @abstractmethod
    def save_chunks(self, chunks: list[CodeChunk]) -> None:
        """
        Persiste uma lista de chunks com seus embeddings no banco vetorial.

        Args:
            chunks: Lista de CodeChunk já com o campo `embedding` preenchido.
        """
        ...

    @abstractmethod
    def search(
        self,
        embedding: list[float],
        repo_id: UUID,
        top_k: int,
    ) -> list[CodeChunk]:
        """
        Busca os chunks mais similares semanticamente ao embedding da query.

        Args:
            embedding: Vetor da pergunta do usuário, já gerado pelo EmbeddingProvider.
            repo_id:   Filtra a busca apenas para chunks deste repositório.
            top_k:     Quantidade máxima de chunks a retornar.

        Returns:
            Lista de CodeChunk ordenada por similaridade (mais próximo primeiro).
        """
        ...

