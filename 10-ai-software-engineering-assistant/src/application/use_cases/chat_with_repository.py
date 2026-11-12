"""
Use Case: ChatWithRepository — Card 4.1

Responsável por orquestrar o fluxo completo de RAG (Retrieval-Augmented Generation)
para responder perguntas sobre um repositório já indexado:
  1. Valida que o repositório existe e está com status "ready"
  2. Gera o embedding da pergunta via EmbeddingProvider
  3. Busca os top-K chunks mais similares no VectorStore
  4. Monta o prompt com instrução de sistema + contexto dos chunks + pergunta
  5. Chama o LLM via LLMProvider
  6. Retorna ChatResponseDTO com a resposta e os arquivos-fonte usados

Características:
  - Stateless: cada requisição é independente, sem histórico persistido.
  - Clean Architecture: depende apenas de interfaces (RepositoryStore,
    EmbeddingProvider, VectorStore, LLMProvider) e entidades/exceções de domínio.
"""

import logging

from src.application.dtos.chat_request_dto import ChatRequestDTO
from src.application.dtos.chat_response_dto import ChatResponseDTO
from src.application.interfaces.embedding_provider import EmbeddingProvider
from src.application.interfaces.llm_provider import LLMProvider
from src.application.interfaces.repository_store import RepositoryStore
from src.application.interfaces.vector_store import VectorStore
from src.domain.entities.code_chunk import CodeChunk
from src.domain.entities.repository import RepositoryStatus
from src.domain.exceptions import RepositoryNotFound, RepositoryNotReady

logger = logging.getLogger(__name__)


class ChatWithRepository:
    def __init__(
        self,
        repository_store: RepositoryStore,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        llm_provider: LLMProvider,
        top_k: int = 5,
    ) -> None:
        self.repository_store = repository_store
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.llm_provider = llm_provider
        self.top_k = top_k

    def execute(self, dto: ChatRequestDTO) -> ChatResponseDTO:
        """
        Executa uma consulta RAG stateless sobre o repositório especificado.

        Args:
            dto: ChatRequestDTO contendo repo_id e question.

        Returns:
            ChatResponseDTO com a resposta gerada e lista de file_path únicos
            ordenados por relevância.

        Raises:
            RepositoryNotFound: Se o repositório não existir.
            RepositoryNotReady: Se o repositório não estiver com status 'ready'.
        """
        # 1. Validar existência e prontidão do repositório
        repository = self.repository_store.get_by_id(dto.repo_id)
        if not repository:
            raise RepositoryNotFound(str(dto.repo_id))

        if repository.status != RepositoryStatus.READY:
            raise RepositoryNotReady(str(dto.repo_id), repository.status.value)

        logger.info(
            "Processando pergunta para repositório '%s' (%s)",
            repository.name,
            dto.repo_id,
        )

        # 2. Gerar embedding da pergunta
        question_embedding = self.embedding_provider.embed(dto.question)

        # 3. Buscar top-K chunks semanticamente similares
        chunks = self.vector_store.search(
            embedding=question_embedding,
            repo_id=dto.repo_id,
            top_k=self.top_k,
        )
        logger.info(
            "Recuperados %d chunk(s) relevantes para repo %s (top_k=%d)",
            len(chunks),
            dto.repo_id,
            self.top_k,
        )

        # 4. Montar prompt com instrução de sistema + contexto + pergunta
        prompt = self._build_prompt(
            repo_name=repository.name,
            chunks=chunks,
            question=dto.question,
        )

        # 5. Chamar LLM
        answer = self.llm_provider.complete(prompt)

        # 6. Extrair caminhos únicos preservando ordem de similaridade
        sources = list(dict.fromkeys(chunk.file_path for chunk in chunks))

        return ChatResponseDTO(
            answer=answer,
            sources=sources,
        )

    @staticmethod
    def _build_prompt(
        repo_name: str,
        chunks: list[CodeChunk],
        question: str,
    ) -> str:
        """Monta o prompt estruturado para o LLM com os trechos de código recuperados."""
        if chunks:
            context_blocks = [
                (
                    f"--- Arquivo: {chunk.file_path} (chunk #{chunk.chunk_index}) ---\n"
                    f"```\n{chunk.content}\n```"
                )
                for chunk in chunks
            ]
            context_text = "\n\n".join(context_blocks)
        else:
            context_text = "(Nenhum trecho de código relevante foi encontrado no índice.)"

        return (
            f"Você é um engenheiro de software sênior analisando o repositório '{repo_name}'.\n"
            "Responda à pergunta do usuário com base EXCLUSIVAMENTE nos trechos de código "
            "fornecidos abaixo no contexto.\n"
            "Regras:\n"
            "- Cite os caminhos dos arquivos relevantes na sua explicação.\n"
            "- Se o contexto fornecido não contiver informação suficiente para responder com "
            "segurança, diga claramente o que está faltando em vez de inventar detalhes.\n"
            "- Seja claro, direto e técnico.\n\n"
            f"### Contexto do Repositório\n{context_text}\n\n"
            f"### Pergunta do Usuário\n{question}\n"
        )
