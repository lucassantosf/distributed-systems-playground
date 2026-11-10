"""
OpenAIEmbeddingProvider — Card 3.3

Implementação concreta de EmbeddingProvider que usa a OpenAI Embeddings API.

Responsabilidades:
  - Implementar o contrato EmbeddingProvider (método embed)
  - Processar chunks em batches para respeitar rate limits da API
  - Logar progresso durante o processamento em batch
  - Isolar o SDK da OpenAI na camada de infraestrutura
    (Use Cases dependem apenas da interface, nunca deste módulo diretamente)

Referência de modelos:
  - text-embedding-3-small : 1536 dimensões, custo baixo, uso recomendado
  - text-embedding-3-large : 3072 dimensões, maior precisão, custo maior
  - text-embedding-ada-002 : legado, 1536 dimensões
"""

import logging
from uuid import UUID

from openai import OpenAI

from src.application.interfaces.embedding_provider import EmbeddingProvider
from src.settings import settings

logger = logging.getLogger(__name__)

# Número máximo de textos por chamada à API (limite conservador de rate)
BATCH_SIZE: int = 20


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    Gera embeddings vetoriais usando a OpenAI Embeddings API.

    Aceita um `repo_id` opcional para enriquecer os logs de progresso.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
    ) -> None:
        self._model = model or settings.embedding_model
        self._client = OpenAI(api_key=api_key or settings.openai_api_key)

    # ------------------------------------------------------------------
    # Contrato público (EmbeddingProvider)
    # ------------------------------------------------------------------

    def embed(self, text: str) -> list[float]:
        """
        Gera o embedding de um único texto.

        Args:
            text: Conteúdo a ser vetorizado (chunk de código ou query do usuário).

        Returns:
            Lista de floats representando o vetor de embedding.
        """
        response = self._client.embeddings.create(
            input=[text],
            model=self._model,
        )
        return response.data[0].embedding

    # ------------------------------------------------------------------
    # Método auxiliar para processamento em batch (usado pelo Use Case
    # via chamadas a embed(), ou diretamente quando se tem a lista completa)
    # ------------------------------------------------------------------

    def embed_many(
        self,
        texts: list[str],
        repo_id: UUID | None = None,
        batch_size: int = BATCH_SIZE,
    ) -> list[list[float]]:
        """
        Gera embeddings para uma lista de textos processando em batches.

        Divide a lista em lotes de `batch_size` para evitar erros de rate
        limit e timeouts na API.

        Args:
            texts: Lista de textos a vetorizar.
            repo_id: Identificador do repositório (apenas para log de progresso).
            batch_size: Tamanho do lote por requisição (default: 20).

        Returns:
            Lista de vetores na mesma ordem dos textos de entrada.
        """
        if not texts:
            return []

        total = len(texts)
        repo_label = str(repo_id) if repo_id else "N/A"
        all_embeddings: list[list[float]] = []

        for start in range(0, total, batch_size):
            batch = texts[start : start + batch_size]

            response = self._client.embeddings.create(
                input=batch,
                model=self._model,
            )

            # A API garante que a ordem dos embeddings espelha a ordem do input
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

            embedded_so_far = min(start + batch_size, total)
            logger.info(
                "Embedded %d/%d chunks para repo %s",
                embedded_so_far,
                total,
                repo_label,
            )

        return all_embeddings
