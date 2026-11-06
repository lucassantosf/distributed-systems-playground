"""
Contrato: LLMProvider

Define como qualquer provedor de LLM deve se comportar.
O Use Case depende desta abstração — nunca da OpenAI diretamente.

Implementação concreta: infrastructure/llm/openai_llm_provider.py
"""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str) -> str:
        """
        Envia um prompt ao LLM e retorna a resposta gerada.

        Args:
            prompt: Texto completo do prompt já montado pelo Use Case
                    (instrução de sistema + contexto dos chunks + pergunta do usuário).

        Returns:
            Texto da resposta gerada pelo modelo.
        """
        ...

