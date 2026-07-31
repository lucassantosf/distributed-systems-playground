from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://cqrs:cqrs_pass@postgres:5432/command_db"
    broker_host: str = "rabbitmq"

    class Config:
        env_file = ".env"


settings = Settings()
