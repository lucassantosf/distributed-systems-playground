"""
Exceções de domínio.

Ficam no domínio porque representam situações de negócio inválidas,
não erros de infraestrutura. Os Use Cases as levantam; a camada de
apresentação as captura e converte em respostas HTTP adequadas.
"""


class RepositoryNotFound(Exception):
    """Levantada quando um repositório não existe no sistema."""

    def __init__(self, repo_id: str) -> None:
        super().__init__(f"Repository not found: {repo_id}")


class RepositoryNotReady(Exception):
    """Levantada quando uma operação requer status 'ready', mas o repo ainda está sendo indexado."""

    def __init__(self, repo_id: str, current_status: str) -> None:
        super().__init__(
            f"Repository '{repo_id}' is not ready for queries (current status: {current_status})"
        )
