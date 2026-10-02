from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Keycloak — para validar token do BFF (Client Credentials) (Card 21)
    keycloak_url: str = "http://keycloak:8080"
    keycloak_issuer_url: str = "http://localhost:8080"
    realm: str = "distributed-systems"

    # Client ID esperado no token de serviço (quem pode nos chamar)
    expected_client_id: str = "bff-client"

    class Config:
        env_file = ".env"


settings = Settings()
