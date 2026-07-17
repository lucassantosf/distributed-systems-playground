from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SERVICE_NAME: str = "user-service"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/user_db"

    class Config:
        env_file = ".env"

settings = Settings()
