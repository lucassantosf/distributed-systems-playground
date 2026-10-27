from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/saga_db"
    REDIS_URL: str = "redis://redis:6379/0"

    # Configuração de Resiliência (Card 5.4)
    # Defaults de produção: 30s timeout, 3 tentativas, 1.0s base delay.
    # No docker-compose.yml estes valores são acelerados (5s / 0.5s) para testes rápidos.
    STEP_TIMEOUT_SECONDS: int = 30
    STEP_MAX_ATTEMPTS: int = 3
    RETRY_BASE_DELAY_SECONDS: float = 1.0

    # RabbitMQ Topology Config
    EXCHANGE_COMMANDS: str = "saga.commands"
    QUEUE_REPLIES: str = "saga.replies"
    EXCHANGE_DLX: str = "saga.dlx"
    QUEUE_DLQ: str = "saga.dlq"

    # Services and command queues
    SERVICES: list[str] = ["inventory", "payment", "shipping", "notification"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

