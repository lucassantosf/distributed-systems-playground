import logging
from src.application.dtos.ingest_repository_dto import IngestRepositoryDTO
from src.domain.entities.repository import RepositoryStatus
from src.infrastructure.persistence.database import SessionLocal
from src.infrastructure.persistence.pg_repository_store import PgRepositoryStore

logger = logging.getLogger(__name__)


class IngestRepository:
    def __init__(self):
        pass

    async def execute(self, dto: IngestRepositoryDTO) -> None:
        """
        Executa a ingestão do repositório em background.
        Utiliza sua própria sessão de banco de dados para não depender do ciclo de vida da request HTTP.
        """
        logger.info(f"Iniciando ingestão do repositório {dto.repo_id} ({dto.github_url})")
        with SessionLocal() as db:
            store = PgRepositoryStore(db)
            try:
                store.update_status(dto.repo_id, RepositoryStatus.INDEXING)
                # Placeholder para os passos do Epic 3:
                # 1. Obter arquivos via RepositoryProvider
                # 2. Dividir arquivos com CodeChunker
                # 3. Gerar embeddings com EmbeddingProvider
                # 4. Salvar chunks com VectorStore
                store.update_status(dto.repo_id, RepositoryStatus.READY)
                logger.info(f"Ingestão do repositório {dto.repo_id} concluída com sucesso")
            except Exception as e:
                logger.error(f"Erro durante ingestão do repositório {dto.repo_id}: {e}", exc_info=True)
                store.update_status(dto.repo_id, RepositoryStatus.ERROR)
