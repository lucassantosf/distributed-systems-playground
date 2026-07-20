from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "product-service"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/product_db"

    class Config:
        env_file = ".env"


settings = Settings()
