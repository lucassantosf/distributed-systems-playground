"""
GeminiEmbeddingProvider — Alternativa gratuita ao OpenAIEmbeddingProvider

Implementação concreta de EmbeddingProvider que usa a Google Gemini Embeddings API
(disponível no plano gratuito do Google AI Studio — sem cartão de crédito necessário).

Modelo padrão: gemini-embedding-001
  - Dimensões nativas: 3072
  - Com output_dimensionality=1536: compatível com a coluna Vector(1536) já criada
    no pgvector sem precisar de nova migration.
  - Rate limit free tier: ~100 req/min, ~1.000 req/dia

Como obter a GEMINI_API_KEY:
  - Acesse https://aistudio.google.com/apikey
  - Clique em "Create API key" (gratuito, sem cartão)
  - Adicione ao .env: GEMINI_API_KEY=AIza...

Troca de provedor:
  - Mude EMBEDDING_PROVIDER=gemini no .env
  - O código das Use Cases e do domínio não precisa ser alterado
"""

import logging
from uuid import UUID

from google import genai
from google.genai import types

from src.application.interfaces.embedding_provider import EmbeddingProvider
from src.settings import settings

logger = logging.getLogger(__name__)

# Dimensão de saída forçada para compatibilidade com Vector(1536) no pgvector.
# O modelo gemini-embedding-001 suporta MRL (Matryoshka Representation Learning),
# permitindo truncar de 3072 → 1536 sem perda catastrófica de qualidade.
OUTPUT_DIMENSIONALITY: int = 1536

# Lote máximo conservador para o free tier (~100 req/min)
BATCH_SIZE: int = 50


class GeminiEmbeddingProvider(EmbeddingProvider):
    """
    Gera embeddings vetoriais usando a Google Gemini Embeddings API.
    Compatible com o plano gratuito do Google AI Studio.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        output_dimensionality: int = OUTPUT_DIMENSIONALITY,
    ) -> None:
        self._model = model or settings.gemini_embedding_model
        self._output_dim = output_dimensionality
        self._client = genai.Client(api_key=api_key or settings.gemini_api_key)

    # ------------------------------------------------------------------
    # Contrato público (EmbeddingProvider)
    # ------------------------------------------------------------------

    def embed(self, text: str) -> list[float]:
        """
        Gera o embedding de um único texto.

        Args:
            text: Conteúdo a ser vetorizado (chunk de código ou query do usuário).

        Returns:
            Lista de floats com OUTPUT_DIMENSIONALITY dimensões.
        """
        response = self._client.models.embed_content(
            model=self._model,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=self._output_dim,
            ),
        )
        return list(response.embeddings[0].values)

    def embed_many(
        self,
        texts: list[str],
        repo_id: UUID | None = None,
        batch_size: int = BATCH_SIZE,
        **kwargs,
    ) -> list[list[float]]:
        """
        Gera embeddings para uma lista de textos processando em batches.

        O Gemini Embeddings API aceita múltiplos conteúdos por requisição.
        Usamos batches para respeitar o rate limit do plano gratuito.

        Args:
            texts: Lista de textos a vetorizar.
            repo_id: Identificador do repositório (apenas para log de progresso).
            batch_size: Tamanho do lote por requisição (default: 50).

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

            response = self._client.models.embed_content(
                model=self._model,
                contents=batch,
                config=types.EmbedContentConfig(
                    output_dimensionality=self._output_dim,
                ),
            )

            # A API garante que a ordem dos embeddings espelha a ordem do input
            batch_embeddings = [list(item.values) for item in response.embeddings]
            all_embeddings.extend(batch_embeddings)

            embedded_so_far = min(start + batch_size, total)
            logger.info(
                "Embedded %d/%d chunks para repo %s (Gemini)",
                embedded_so_far,
                total,
                repo_label,
            )

        return all_embeddings
