from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@db:5432/ai_assistant"

    # OpenAI
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"

    # Google Gemini
    gemini_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_llm_model: str = "gemini-3.5-flash"

    # Seleção de provedor: "gemini" (padrão) | "openai"
    # Alterne no .env sem alterar nenhum código de domínio ou use case.
    embedding_provider: str = "gemini"
    llm_provider: str = "gemini"

    # Configurações compartilhadas
    github_token: str = ""
    vector_search_top_k: int = 5


settings = Settings()

