from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    PROJECT_NAME: str = "Event-Driven Orders API"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    DATABASE_URL: str = "postgresql://orders_user:orders_password@localhost:5432/orders_db"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_AMQP_PORT: int = 5672
    RABBITMQ_USER: str = Field("guest", env="RABBITMQ_DEFAULT_USER")
    RABBITMQ_PASS: str = Field("guest", env="RABBITMQ_DEFAULT_PASS")
    RABBITMQ_QUEUE: str = "orders"

    model_config = {"env_file": ".env"}


settings = Settings()
