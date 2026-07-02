from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://chatuser:chatpass@localhost:5432/chatdb"
    redis_url: str = "redis://localhost:6379"

    class Config:
        env_file = ".env"


settings = Settings()
