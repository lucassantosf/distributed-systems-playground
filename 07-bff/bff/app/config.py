from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    user_service_url: str = "http://user-service:8001"
    product_service_url: str = "http://product-service:8002"
    order_service_url: str = "http://order-service:8003"
    downstream_timeout: float = 5.0

    model_config = {"env_file": ".env"}

settings = Settings()
