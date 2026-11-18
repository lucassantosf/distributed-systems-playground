"""
DTO: ChatResponseDTO

Carrega os dados de saída do Use Case ChatWithRepository.
F2-2: adiciona conversation_id para que o frontend rastreie a conversa.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass
class ChatResponseDTO:
    answer: str                # Resposta gerada pelo LLM
    sources: list[str]         # Lista de file_path dos chunks usados como contexto
    conversation_id: UUID      # ID da conversa (nova ou retomada)

