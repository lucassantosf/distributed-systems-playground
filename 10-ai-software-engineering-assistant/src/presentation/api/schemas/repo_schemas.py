import re
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

from src.application.dtos.ingest_repository_dto import IngestRepositoryDTO


GITHUB_REPO_URL_REGEX = re.compile(
    r"^https://github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)$"
)


class CreateRepositoryRequest(BaseModel):
    github_url: str = Field(
        ...,
        description="URL pública do repositório no GitHub (ex: https://github.com/owner/repo)",
        examples=["https://github.com/fastapi/fastapi"],
    )

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        clean_url = v.strip().rstrip("/")
        match = GITHUB_REPO_URL_REGEX.match(clean_url)
        if not match:
            raise ValueError(
                "URL do GitHub inválida. Deve seguir o formato: https://github.com/owner/repo"
            )
        return clean_url

    def extract_repo_name(self) -> str:
        clean_url = self.github_url.strip().rstrip("/")
        match = GITHUB_REPO_URL_REGEX.match(clean_url)
        if match:
            return match.group(2)
        return clean_url.split("/")[-1]

    def to_dto(self, repo_id: UUID) -> IngestRepositoryDTO:
        return IngestRepositoryDTO(repo_id=repo_id, github_url=self.github_url)


class CreateRepositoryResponse(BaseModel):
    id: UUID
    status: str


class RepositoryResponse(BaseModel):
    id: UUID
    github_url: str
    name: str
    status: str
    created_at: datetime
    indexed_at: datetime | None = None

