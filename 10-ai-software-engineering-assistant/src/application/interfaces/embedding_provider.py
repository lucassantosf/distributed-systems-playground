"""
Contrato: EmbeddingProvider

Define como qualquer provedor de embeddings deve se comportar.
O Use Case depende desta abstração — nunca da OpenAI diretamente.

Implementação concreta: infrastructure/embeddings/openai_embedding_provider.py
"""

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """
        Gera um vetor de embedding para o texto fornecido.

        Args:
            text: Texto a ser vetorizado (chunk de código ou pergunta do usuário).

        Returns:
            Lista de floats representando o vetor de embedding.
        """
        ...

    def embed_many(self, texts: list[str], **kwargs) -> list[list[float]]:
        """
        Gera embeddings para uma lista de textos.

        Implementação padrão: chama embed() sequencialmente.
        Implementações concretas podem sobrescrever para usar batch processing.

        Args:
            texts: Lista de textos a vetorizar.
            **kwargs: Argumentos extras aceitos por implementações concretas
                      (ex: repo_id, batch_size).

        Returns:
            Lista de vetores na mesma ordem dos textos de entrada.
        """
        return [self.embed(text) for text in texts]

