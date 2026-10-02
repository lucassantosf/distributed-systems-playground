from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Keycloak — para validar token do usuário (Card 19)
    keycloak_url: str = "http://keycloak:8080"
    keycloak_issuer_url: str = "http://localhost:8080"
    realm: str = "distributed-systems"

    # Client ID/Secret do próprio BFF — para Client Credentials (Card 20)
    client_id: str = "bff-client"
    client_secret: str = ""

    # URL interna do docs-service (dentro da rede Docker)
    docs_service_url: str = "http://docs-service:8003"

    class Config:
        env_file = ".env"


settings = Settings()
