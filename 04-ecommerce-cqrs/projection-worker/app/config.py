from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    broker_host: str = "rabbitmq"
    redis_url: str = "redis://redis:6379/0"
    projection_delay_seconds: float = 0.0
    max_retries: int = 3
    retry_base_delay_seconds: float = 1.0
    dlq_exchange: str = "product_events.dlx"
    dlq_queue: str = "product_events.dlq"

    class Config:
        env_file = ".env"


settings = Settings()
