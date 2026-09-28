from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # URL interna (Docker network) — usada para buscar o JWKS
    keycloak_url: str = "http://keycloak:8080"

    # URL do issuer conforme emitida pelo Keycloak no claim "iss" do JWT.
    # O Keycloak usa o hostname pelo qual foi acessado na requisição de token.
    # Em dev, tokens são obtidos via localhost:8080, então o iss é localhost:8080.
    # Em produção, este valor seria o hostname público do Keycloak.
    keycloak_issuer_url: str = "http://localhost:8080"

    realm: str = "distributed-systems"
    client_id: str = "api-simples"
    client_secret: str = "GZYImUZPV2W7tWzsQKTbpzdNFI2eLdGC"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
