from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "order-service"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/order_db"

    class Config:
        env_file = ".env"


settings = Settings()
