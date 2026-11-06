"""
DTO: ChatResponseDTO

Carrega os dados de saída do Use Case ChatWithRepository.
"""

from dataclasses import dataclass


@dataclass
class ChatResponseDTO:
    answer: str                # Resposta gerada pelo LLM
    sources: list[str]         # Lista de file_path dos chunks usados como contexto

