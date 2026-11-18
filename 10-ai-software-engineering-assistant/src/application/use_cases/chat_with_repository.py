"""
Use Case: ChatWithRepository — Card 4.1 + F2-2

Responsável por orquestrar o fluxo completo de RAG (Retrieval-Augmented Generation)
para responder perguntas sobre um repositório já indexado:
  1. Valida que o repositório existe e está com status "ready"
  2. Cria ou retoma uma Conversation (F2-2)
  3. Persiste a mensagem do usuário (F2-2)
  4. Gera o embedding da pergunta via EmbeddingProvider
  5. Busca os top-K chunks mais similares no VectorStore
  6. Monta o prompt com instrução de sistema + histórico + contexto + pergunta
  7. Chama o LLM via LLMProvider
  8. Persiste a resposta do assistente (F2-2)
  9. Retorna ChatResponseDTO com resposta, fontes e conversation_id

Características:
  - Stateful: cada requisição é vinculada a uma Conversation persistida (F2-2).
  - Clean Architecture: depende apenas de interfaces (RepositoryStore,
    EmbeddingProvider, VectorStore, LLMProvider, ConversationStore) e entidades/exceções de domínio.
"""

import logging
from uuid import uuid4

from src.application.dtos.chat_request_dto import ChatRequestDTO
from src.application.dtos.chat_response_dto import ChatResponseDTO
from src.application.interfaces.conversation_store import ConversationStore
from src.application.interfaces.embedding_provider import EmbeddingProvider
from src.application.interfaces.llm_provider import LLMProvider
from src.application.interfaces.repository_store import RepositoryStore
from src.application.interfaces.vector_store import VectorStore
from src.domain.entities.code_chunk import CodeChunk
from src.domain.entities.conversation import Conversation, ConversationMessage
from src.domain.entities.repository import RepositoryStatus
from src.domain.exceptions import RepositoryNotFound, RepositoryNotReady

logger = logging.getLogger(__name__)

# Número de pares (user, assistant) a incluir no contexto de histórico
HISTORY_PAIRS = 5


class ChatWithRepository:
    def __init__(
        self,
        repository_store: RepositoryStore,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        llm_provider: LLMProvider,
        conversation_store: ConversationStore,
        top_k: int = 5,
    ) -> None:
        self.repository_store = repository_store
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.llm_provider = llm_provider
        self.conversation_store = conversation_store
        self.top_k = top_k

    def execute(self, dto: ChatRequestDTO) -> ChatResponseDTO:
        """
        Executa uma consulta RAG stateful sobre o repositório especificado.

        Args:
            dto: ChatRequestDTO contendo repo_id, question e conversation_id opcional.

        Returns:
            ChatResponseDTO com a resposta gerada, lista de file_path e conversation_id.

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

        # 2. Criar ou retomar conversa
        if dto.conversation_id:
            conversation = self.conversation_store.get_by_id(dto.conversation_id)
            if not conversation:
                # ID inválido → cria uma nova silenciosamente
                logger.warning(
                    "conversation_id %s não encontrado, criando nova conversa",
                    dto.conversation_id,
                )
                conversation = self._create_conversation(dto.question, dto.repo_id)
            else:
                logger.info("Retomando conversa %s", conversation.id)
        else:
            conversation = self._create_conversation(dto.question, dto.repo_id)

        # 3. Persistir mensagem do usuário
        user_message = ConversationMessage(
            id=uuid4(),
            conversation_id=conversation.id,
            role="user",
            content=dto.question,
            sources=[],
        )
        self.conversation_store.add_message(user_message)

        # 4. Carregar histórico recente para enriquecer o prompt
        history = self.conversation_store.get_messages(
            conversation.id, limit=HISTORY_PAIRS * 2 + 1
        )
        # Exclui a mensagem do usuário que acabou de ser salva (última)
        history_for_prompt = history[:-1] if history else []

        # 5. Gerar embedding da pergunta
        question_embedding = self.embedding_provider.embed(dto.question)

        # 6. Buscar top-K chunks semanticamente similares
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

        # 7. Montar prompt com histórico + contexto + pergunta
        prompt = self._build_prompt(
            repo_name=repository.name,
            chunks=chunks,
            question=dto.question,
            history=history_for_prompt,
        )

        # 8. Chamar LLM
        answer = self.llm_provider.complete(prompt)

        # 9. Extrair caminhos únicos preservando ordem de similaridade
        sources = list(dict.fromkeys(chunk.file_path for chunk in chunks))

        # 10. Persistir resposta do assistente e atualizar updated_at
        assistant_message = ConversationMessage(
            id=uuid4(),
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            sources=sources,
        )
        self.conversation_store.add_message(assistant_message)
        self.conversation_store.touch(conversation.id)

        return ChatResponseDTO(
            answer=answer,
            sources=sources,
            conversation_id=conversation.id,
        )

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    def _create_conversation(self, first_question: str, repo_id) -> Conversation:
        """Cria e persiste uma nova conversa com título derivado da primeira pergunta."""
        title = first_question[:100] if first_question else "Nova conversa"
        conversation = Conversation.create(repo_id=repo_id, title=title)
        return self.conversation_store.create(conversation)

    @staticmethod
    def _build_prompt(
        repo_name: str,
        chunks: list[CodeChunk],
        question: str,
        history: list[ConversationMessage],
    ) -> str:
        """Monta o prompt estruturado para o LLM com histórico + trechos de código."""
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

        # Monta seção de histórico (se houver)
        history_section = ""
        if history:
            history_lines = []
            for msg in history:
                prefix = "Usuário" if msg.role == "user" else "Assistente"
                history_lines.append(f"{prefix}: {msg.content}")
            history_section = (
                "### Histórico da Conversa\n"
                + "\n".join(history_lines)
                + "\n\n"
            )

        return (
            f"Você é um engenheiro de software sênior analisando o repositório '{repo_name}'.\n"
            "Responda à pergunta do usuário com base EXCLUSIVAMENTE nos trechos de código "
            "fornecidos abaixo no contexto.\n"
            "Regras:\n"
            "- Cite os caminhos dos arquivos relevantes na sua explicação.\n"
            "- Se o contexto fornecido não contiver informação suficiente para responder com "
            "segurança, diga claramente o que está faltando em vez de inventar detalhes.\n"
            "- Seja claro, direto e técnico.\n"
            "- Leve em conta o histórico da conversa para manter coerência e continuidade.\n\n"
            f"{history_section}"
            f"### Contexto do Repositório\n{context_text}\n\n"
            f"### Pergunta do Usuário\n{question}\n"
        )
