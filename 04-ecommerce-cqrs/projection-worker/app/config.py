from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    broker_host: str = "rabbitmq"
    redis_url: str = "redis://redis:6379/0"

    class Config:
        env_file = ".env"


settings = Settings()
