"""
Ponto central de injeção de dependências (Composition Root / Dependency Container).

Responsabilidades:
1. Instanciar as implementações de infraestrutura (banco, APIs externas, background jobs).
2. Fornecer instâncias tipadas das interfaces (contratos de application/interfaces).
3. Montar e entregar instâncias dos Use Cases já configurados com suas dependências via FastAPI Depends.

À medida que os cards dos Epics 2, 3 e 4 forem implementados, suas respectivas
classes concretas serão vinculadas aqui.
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from src.infrastructure.persistence.database import get_db

# Tipo auxiliar para injeção da sessão do SQLAlchemy nas rotas ou providers
DatabaseSession = Annotated[Session, Depends(get_db)]


# ==============================================================================
# Providers de Infraestrutura (serão conectados conforme os cards de infra)
# ==============================================================================

# Exemplos e estruturas para os próximos cards:
#
# def get_repository_store(db: DatabaseSession) -> RepositoryStore:
#     return PgRepositoryStore(db)
#
# def get_vector_store(db: DatabaseSession) -> VectorStore:
#     return PgVectorStore(db)
#
# def get_embedding_provider() -> EmbeddingProvider:
#     return OpenAIEmbeddingProvider(api_key=settings.openai_api_key)
#
# def get_llm_provider() -> LLMProvider:
#     return OpenAILLMProvider(api_key=settings.openai_api_key)
#
# def get_task_dispatcher() -> TaskDispatcher:
#     return AsyncioTaskDispatcher()


# ==============================================================================
# Injeção de Use Cases (camada de Application)
# ==============================================================================

# def get_ingest_repository_use_case(...) -> IngestRepository:
#     ...
#
# def get_chat_with_repository_use_case(...) -> ChatWithRepository:
#     ...
