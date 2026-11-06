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

