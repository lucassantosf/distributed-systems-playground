import logging
import re
from typing import Callable

from src.application.dtos.file_content_dto import FileContentDTO
from src.application.dtos.ingest_repository_dto import IngestRepositoryDTO
from src.application.interfaces.embedding_provider import EmbeddingProvider
from src.application.interfaces.repository_provider import RepositoryProvider
from src.application.interfaces.repository_store import RepositoryStore
from src.application.interfaces.vector_store import VectorStore
from src.domain.entities.code_chunk import CodeChunk
from src.domain.entities.repository import RepositoryStatus

logger = logging.getLogger(__name__)

GITHUB_URL_PATTERN = re.compile(
    r"^https://github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)$"
)


class IngestRepository:
    def __init__(
        self,
        repository_store_factory: Callable[[], RepositoryStore],
        repository_provider: RepositoryProvider,
        embedding_provider: EmbeddingProvider | None,
        vector_store_factory: Callable[[], VectorStore] | None,
        chunker: Callable[[list[FileContentDTO], any], list[CodeChunk]] | None = None,
    ):
        """
        Args:
            repository_store_factory: Callable sem argumentos que retorna um novo
                RepositoryStore com sua própria sessão de banco. Necessário porque
                o Use Case roda em background (após o request HTTP fechar),
                logo não pode reusar a sessão SQLAlchemy do request.
            vector_store_factory: Callable sem argumentos que retorna um novo
                VectorStore com sua própria sessão de banco. Mesmo motivo acima.
                Pode ser None enquanto Card 3.4 não estiver completo.
        """
        self.repository_store_factory = repository_store_factory
        self.repository_provider = repository_provider
        self.embedding_provider = embedding_provider
        self.vector_store_factory = vector_store_factory
        self.chunker = chunker

    async def execute(self, dto: IngestRepositoryDTO) -> None:
        """
        Orquestra o pipeline completo de ingestão:
        1. Cria sessão de banco própria (independente do request HTTP)
        2. Atualiza status para 'indexing'
        3. Extrai owner e repo da URL e lista/baixa arquivos via RepositoryProvider
        4. Quebra os arquivos em chunks via chunker
        5. Gera embeddings para os chunks via EmbeddingProvider
        6. Persiste chunks e vetores via VectorStore
        7. Atualiza status para 'ready' (ou 'error' em caso de falha)
        """
        logger.info(f"Iniciando ingestão do repositório {dto.repo_id} ({dto.github_url})")

        # 1. Cria repositório store com sessão própria para o background job
        repository_store: RepositoryStore = self.repository_store_factory()

        try:
            # 2. Atualiza status para indexing
            repository_store.update_status(dto.repo_id, RepositoryStatus.INDEXING)

            # 3. Extrair owner e repo e baixar arquivos via RepositoryProvider
            owner, repo = self._parse_github_url(dto.github_url)
            files = self.repository_provider.list_files(owner, repo)
            logger.info(f"Recuperados {len(files)} arquivos do repositório {owner}/{repo}")

            # 4. Gerar chunks
            chunks: list[CodeChunk] = []
            if self.chunker:
                chunks = self.chunker(files, dto.repo_id)
            else:
                # Fallback simples: 1 chunk por arquivo caso chunker ainda não esteja conectado
                for idx, file_dto in enumerate(files):
                    chunks.append(
                        CodeChunk(
                            repository_id=dto.repo_id,
                            file_path=file_dto.path,
                            content=file_dto.content,
                            chunk_index=idx,
                        )
                    )
            logger.info(f"Total de {len(chunks)} chunks gerados para o repositório {dto.repo_id}")

            if not chunks:
                raise ValueError(
                    f"Nenhum arquivo com extensão suportada ou conteúdo válido encontrado em {owner}/{repo}"
                )

            # 4. Gerar embeddings em batch (skipa enquanto EmbeddingProvider não estiver disponível — card 3.3)
            if self.embedding_provider:
                texts = [chunk.content for chunk in chunks]
                embeddings = self.embedding_provider.embed_many(texts, repo_id=dto.repo_id)
                for chunk, embedding in zip(chunks, embeddings):
                    chunk.embedding = embedding
            else:
                logger.warning(
                    "EmbeddingProvider não configurado — embeddings não gerados (card 3.3 pendente)"
                )

            # 5. Persistir no VectorStore
            if self.vector_store_factory and chunks:
                vector_store: VectorStore = self.vector_store_factory()
                vector_store.save_chunks(chunks)
            elif chunks:
                logger.warning(
                    "VectorStore não configurado — %d chunk(s) não persistidos (card 3.4 pendente)",
                    len(chunks),
                )

            # 6. Atualizar status para ready
            repository_store.update_status(dto.repo_id, RepositoryStatus.READY)
            logger.info(f"Ingestão do repositório {dto.repo_id} concluída com sucesso")

        except Exception as e:
            logger.error(
                f"Erro durante ingestão do repositório {dto.repo_id}: {e}",
                exc_info=True,
            )
            repository_store.update_status(dto.repo_id, RepositoryStatus.ERROR)

    @staticmethod
    def _parse_github_url(url: str) -> tuple[str, str]:
        clean_url = url.strip().rstrip("/")
        match = GITHUB_URL_PATTERN.match(clean_url)
        if match:
            return match.group(1), match.group(2)
        parts = clean_url.split("/")
        return parts[-2], parts[-1]
