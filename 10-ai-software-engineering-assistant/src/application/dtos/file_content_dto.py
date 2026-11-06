"""
DTO: FileContentDTO

Representa um arquivo recuperado do GitHub pelo RepositoryProvider.
É o objeto que trafega entre a infraestrutura (GitHub API) e o Use Case de ingestão.
"""

from dataclasses import dataclass


@dataclass
class FileContentDTO:
    path: str       # Caminho relativo do arquivo no repositório (ex: "src/auth.py")
    content: str    # Conteúdo bruto do arquivo como string

