"""
GeminiLLMProvider — Alternativa gratuita ao OpenAILLMProvider

Implementação concreta de LLMProvider que usa a Google Gemini API
(disponível no plano gratuito do Google AI Studio — sem cartão de crédito necessário).

Responsabilidades:
  - Implementar o contrato LLMProvider (método complete)
  - Encapsular a comunicação com o SDK google-genai na camada de infraestrutura
  - Usar o modelo configurado via GEMINI_LLM_MODEL nas settings

Troca de provedor:
  - Configure LLM_PROVIDER=gemini e GEMINI_API_KEY=... no .env
  - O código dos Use Cases e do domínio não precisa ser alterado
"""

import logging
import time

from google import genai
from google.genai import errors, types

from src.application.interfaces.llm_provider import LLMProvider
from src.settings import settings

logger = logging.getLogger(__name__)

MAX_RETRIES_503: int = 3


class GeminiLLMProvider(LLMProvider):
    """
    Gera respostas em linguagem natural usando a Google Gemini API.
    Compatível com o plano gratuito do Google AI Studio.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        temperature: float = 0.2,
    ) -> None:
        self._model = model or settings.gemini_llm_model
        self._temperature = temperature
        self._client = genai.Client(api_key=api_key or settings.gemini_api_key)

    def complete(self, prompt: str) -> str:
        """
        Envia o prompt montado pelo Use Case para a Gemini API
        e retorna o texto gerado pelo modelo.

        Inclui retry simples para picos transitórios de demanda (503) no free tier.

        Args:
            prompt: Prompt completo (sistema + contexto dos chunks + pergunta).

        Returns:
            Texto da resposta gerada pelo LLM.
        """
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES_503 + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=self._temperature,
                    ),
                )
                content = response.text or ""
                logger.info("Resposta gerada via Gemini (model=%s)", self._model)
                return content.strip()
            except errors.ServerError as exc:
                last_error = exc
                if attempt < MAX_RETRIES_503:
                    wait_seconds = attempt * 1.5
                    logger.warning(
                        "Gemini retornou erro transitório (%s). Tentando novamente em %.1fs (%d/%d)...",
                        exc.code,
                        wait_seconds,
                        attempt,
                        MAX_RETRIES_503,
                    )
                    time.sleep(wait_seconds)
                else:
                    raise

        raise last_error  # pragma: no cover
