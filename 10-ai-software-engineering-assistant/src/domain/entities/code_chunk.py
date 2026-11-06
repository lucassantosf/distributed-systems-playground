"""
Entidade de domínio: CodeChunk

Representa um fragmento de código extraído de um repositório,
pronto para ser indexado com seu embedding vetorial.
Esta classe é pura Python — não conhece SQLAlchemy, pgvector ou qualquer framework.
"""

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass
class CodeChunk:
    repository_id: UUID
    file_path: str
    content: str
    chunk_index: int
    id: UUID = field(default_factory=uuid4)
    # Embedding gerado pelo EmbeddingProvider. None enquanto ainda não foi gerado.
    embedding: list[float] | None = None

