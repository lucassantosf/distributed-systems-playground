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
    RABBITMQ_EXCHANGE: str = "order_events"
    RABBITMQ_EXCHANGE_TYPE: str = "fanout"
    RABBITMQ_DEAD_LETTER_EXCHANGE: str = "order_events_dlx"
    RABBITMQ_EMAIL_QUEUE: str = "email_orders"
    RABBITMQ_EMAIL_RETRY_QUEUE: str = "email_orders_retry"
    RABBITMQ_EMAIL_DLQ_QUEUE: str = "email_orders_dlq"
    RABBITMQ_BILLING_QUEUE: str = "billing_orders"
    RABBITMQ_BILLING_RETRY_QUEUE: str = "billing_orders_retry"
    RABBITMQ_BILLING_DLQ_QUEUE: str = "billing_orders_dlq"
    RABBITMQ_NOTIFICATION_QUEUE: str = "notification_orders"
    RABBITMQ_NOTIFICATION_DLQ_QUEUE: str = "notification_orders_dlq"
    RABBITMQ_RETRY_DELAY_MS: int = 5000
    RABBITMQ_MAX_RETRIES: int = 3

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
