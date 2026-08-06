from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://cqrs:cqrs_pass@postgres:5432/command_db"
    broker_host: str = "rabbitmq"
    dlq_exchange: str = "product_events.dlx"
    dlq_queue: str = "product_events.dlq"

    class Config:
        env_file = ".env"


settings = Settings()
