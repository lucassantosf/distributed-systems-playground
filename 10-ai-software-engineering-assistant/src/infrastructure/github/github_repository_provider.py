import base64
import logging
from typing import Set
import httpx

from src.application.dtos.file_content_dto import FileContentDTO
from src.application.interfaces.repository_provider import RepositoryProvider

logger = logging.getLogger(__name__)


class GithubRepositoryProvider(RepositoryProvider):
    # Extensões relevantes para análise de código e documentação arquitetural
    SUPPORTED_EXTENSIONS: Set[str] = {
        ".py",
        ".ts",
        ".js",
        ".go",
        ".java",
        ".rb",
        ".rs",
        ".md",
    }

    def __init__(self, token: str | None = None, base_url: str = "https://api.github.com"):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AI-Software-Engineering-Assistant",
        }
        if token and token.strip():
            self.headers["Authorization"] = f"Bearer {token.strip()}"

    def list_files(self, owner: str, repo: str) -> list[FileContentDTO]:
        """
        Lista e baixa o conteúdo de arquivos relevantes do repositório no GitHub.
        1. Consulta branch padrão / tree SHA
        2. Lista recursivamente a árvore do git
        3. Filtra extensões suportadas
        4. Baixa o conteúdo dos arquivos
        """
        with httpx.Client(base_url=self.base_url, headers=self.headers, timeout=30.0) as client:
            # 1. Obter branch padrão do repositório
            repo_resp = client.get(f"/repos/{owner}/{repo}")
            self._handle_response_errors(repo_resp, f"repositório {owner}/{repo}")
            default_branch = repo_resp.json().get("default_branch", "main")

            # 2. Obter árvore completa de arquivos recursivamente
            tree_url = f"/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
            tree_resp = client.get(tree_url)
            self._handle_response_errors(tree_resp, f"árvore do repositório {owner}/{repo}")
            
            tree_data = tree_resp.json()
            items = tree_data.get("tree", [])

            # 3. Filtrar arquivos de código com base nas extensões
            matched_files = []
            for item in items:
                if item.get("type") == "blob":
                    path = item.get("path", "")
                    if self._is_supported_extension(path):
                        matched_files.append(path)

            logger.info(f"Encontrados {len(matched_files)} arquivos relevantes em {owner}/{repo}")

            # 4. Baixar conteúdo dos arquivos
            files_content: list[FileContentDTO] = []
            for file_path in matched_files:
                content = self._fetch_file_content(client, owner, repo, file_path)
                if content is not None:
                    files_content.append(FileContentDTO(path=file_path, content=content))

            return files_content

    def _fetch_file_content(
        self, client: httpx.Client, owner: str, repo: str, file_path: str
    ) -> str | None:
        try:
            resp = client.get(f"/repos/{owner}/{repo}/contents/{file_path}")
            if resp.status_code == 200:
                data = resp.json()
                encoding = data.get("encoding")
                raw_content = data.get("content", "")
                if encoding == "base64" and raw_content:
                    return base64.b64decode(raw_content).decode("utf-8", errors="replace")
                return raw_content
            else:
                logger.warning(
                    f"Falha ao baixar {file_path} de {owner}/{repo}: status {resp.status_code}"
                )
                return None
        except Exception as e:
            logger.warning(f"Erro ao obter conteúdo de {file_path}: {e}")
            return None

    def _is_supported_extension(self, path: str) -> bool:
        lower_path = path.lower()
        return any(lower_path.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)

    def _handle_response_errors(self, response: httpx.Response, resource: str) -> None:
        if response.status_code == 403 or response.status_code == 429:
            raise RuntimeError(
                f"Rate limit atingido na GitHub API ao consultar {resource}. "
                "Considere configurar um GITHUB_TOKEN no .env."
            )
        elif response.status_code == 404:
            raise ValueError(f"Recurso não encontrado na GitHub API: {resource}")
        elif response.is_error:
            raise RuntimeError(
                f"Erro na GitHub API ({response.status_code}) ao consultar {resource}: {response.text}"
            )
