"""
Interface (porta) para o armazenamento de conversas — F2-2

Define o contrato que a camada de aplicação usa para persistir e recuperar
conversas sem depender de nenhuma implementação concreta (Clean Architecture).
"""

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.conversation import Conversation, ConversationMessage


class ConversationStore(ABC):
    @abstractmethod
    def create(self, conversation: Conversation) -> Conversation:
        """Persiste uma nova conversa e retorna a entidade salva."""
        ...

    @abstractmethod
    def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        """Retorna a conversa com suas mensagens, ou None se não existir."""
        ...

    @abstractmethod
    def list_by_repo(self, repo_id: UUID) -> list[Conversation]:
        """Lista todas as conversas de um repositório (sem carregar mensagens)."""
        ...

    @abstractmethod
    def add_message(self, message: ConversationMessage) -> ConversationMessage:
        """Persiste uma nova mensagem e retorna a entidade salva."""
        ...

    @abstractmethod
    def get_messages(
        self, conversation_id: UUID, limit: int = 20
    ) -> list[ConversationMessage]:
        """Retorna as últimas `limit` mensagens de uma conversa, em ordem cronológica."""
        ...

    @abstractmethod
    def touch(self, conversation_id: UUID) -> None:
        """Atualiza o `updated_at` da conversa (chamado após cada mensagem)."""
        ...
