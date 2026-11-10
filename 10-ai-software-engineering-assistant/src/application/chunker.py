"""
Code Chunker — Card 3.2

Responsabilidade única: receber uma lista de FileContentDTO e quebrar o conteúdo
de cada arquivo em blocos (chunks) de tamanho fixo com sobreposição (overlap),
retornando uma lista de CodeChunk prontos para embedding.

Estratégia:
  - Tamanho máximo por chunk: MAX_CHUNK_SIZE caracteres (default 1500)
  - Overlap entre chunks consecutivos: OVERLAP_SIZE caracteres (~10%)
  - Arquivos menores que MAX_CHUNK_SIZE → único chunk sem sobreposição
  - Chunk final de um arquivo pode ser menor que MAX_CHUNK_SIZE

Regras de Clean Architecture:
  - Módulo puro Python — sem dependências de infraestrutura
  - Recebe e retorna entidades/DTOs da camada Application/Domain
  - Pode ser passado como Callable para o Use Case IngestRepository
"""

import logging
from uuid import UUID

from src.application.dtos.file_content_dto import FileContentDTO
from src.domain.entities.code_chunk import CodeChunk

logger = logging.getLogger(__name__)

# Tamanho alvo de cada chunk em caracteres
MAX_CHUNK_SIZE: int = 1500
# Sobreposição entre chunks consecutivos (~10% de MAX_CHUNK_SIZE)
OVERLAP_SIZE: int = 150


def chunk_files(
    files: list[FileContentDTO],
    repo_id: UUID,
    *,
    max_chunk_size: int = MAX_CHUNK_SIZE,
    overlap_size: int = OVERLAP_SIZE,
) -> list[CodeChunk]:
    """
    Divide uma lista de arquivos em CodeChunks de tamanho fixo com overlap.

    Args:
        files: Arquivos recuperados do repositório (cada um com path + content).
        repo_id: UUID do repositório pai — copiado para cada chunk gerado.
        max_chunk_size: Número máximo de caracteres por chunk.
        overlap_size: Número de caracteres repetidos entre chunks consecutivos.

    Returns:
        Lista plana de CodeChunk ordenados por arquivo e índice dentro do arquivo.
    """
    if overlap_size >= max_chunk_size:
        raise ValueError(
            f"overlap_size ({overlap_size}) deve ser menor que max_chunk_size ({max_chunk_size})"
        )

    all_chunks: list[CodeChunk] = []

    for file_dto in files:
        content = file_dto.content

        # Arquivo vazio → ignorar
        if not content.strip():
            logger.debug("Arquivo ignorado (vazio): %s", file_dto.path)
            continue

        file_chunks = _split_into_chunks(content, max_chunk_size, overlap_size)

        for chunk_index, chunk_content in enumerate(file_chunks):
            all_chunks.append(
                CodeChunk(
                    repository_id=repo_id,
                    file_path=file_dto.path,
                    content=chunk_content,
                    chunk_index=chunk_index,
                )
            )

        logger.debug(
            "Arquivo '%s' → %d chunk(s) gerado(s)", file_dto.path, len(file_chunks)
        )

    logger.info(
        "Chunking concluído: %d arquivo(s) → %d chunk(s) total para repo %s",
        len(files),
        len(all_chunks),
        repo_id,
    )

    return all_chunks


def _split_into_chunks(
    text: str, max_chunk_size: int, overlap_size: int
) -> list[str]:
    """
    Divide uma string em blocos de até `max_chunk_size` caracteres,
    com `overlap_size` caracteres de sobreposição entre blocos consecutivos.

    Exemplo (max=10, overlap=3):
      text = "ABCDEFGHIJKLMNOP"
      → ["ABCDEFGHIJ", "HIJKLMNOP", "NOP"]  (sliding window)
    """
    if len(text) <= max_chunk_size:
        return [text]

    chunks: list[str] = []
    step = max_chunk_size - overlap_size  # avanço real entre blocos
    start = 0

    while start < len(text):
        end = start + max_chunk_size
        chunk = text[start:end]
        chunks.append(chunk)

        if end >= len(text):
            break

        start += step

    return chunks
