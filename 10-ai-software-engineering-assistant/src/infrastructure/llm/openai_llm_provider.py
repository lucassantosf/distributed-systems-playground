"""
OpenAILLMProvider — Card 4.2

Implementação concreta de LLMProvider que usa a OpenAI Chat Completions API.

Responsabilidades:
  - Implementar o contrato LLMProvider (método complete)
  - Encapsular a comunicação com o SDK da OpenAI na camada de infraestrutura
  - Usar o modelo configurado via LLM_MODEL nas settings

Regras de Clean Architecture:
  - Use Cases dependem apenas da interface LLMProvider, nunca deste módulo.
"""

import logging

from openai import OpenAI

from src.application.interfaces.llm_provider import LLMProvider
from src.settings import settings

logger = logging.getLogger(__name__)


class OpenAILLMProvider(LLMProvider):
    """
    Gera respostas em linguagem natural usando a OpenAI Chat Completions API.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        temperature: float = 0.2,
    ) -> None:
        self._model = model or settings.llm_model
        self._temperature = temperature
        self._client = OpenAI(api_key=api_key or settings.openai_api_key)

    def complete(self, prompt: str) -> str:
        """
        Envia o prompt montado pelo Use Case para a Chat Completions API
        e retorna o texto gerado pelo modelo.

        Args:
            prompt: Prompt completo (sistema + contexto dos chunks + pergunta).

        Returns:
            Texto da resposta gerada pelo LLM.
        """
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._temperature,
        )

        content = response.choices[0].message.content or ""
        logger.info("Resposta gerada via OpenAI (model=%s)", self._model)
        return content.strip()
