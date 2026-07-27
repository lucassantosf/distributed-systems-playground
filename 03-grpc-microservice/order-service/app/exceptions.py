class MicroserviceError(Exception):
    def __init__(self, service: str, message: str, status_code: int = 503):
        self.service = service
        self.message = message
        self.status_code = status_code
        super().__init__(f"{service}: {message}")


class ServiceUnavailableError(MicroserviceError):
    def __init__(self, service: str):
        super().__init__(service, f"{service} is unavailable", 503)


class ServiceTimeoutError(MicroserviceError):
    def __init__(self, service: str):
        super().__init__(service, f"{service} timed out", 504)


class UserNotFoundError(MicroserviceError):
    def __init__(self, user_id: str):
        super().__init__("user-service", f"User {user_id} not found", 404)


class ProductNotFoundError(MicroserviceError):
    def __init__(self, product_id: str):
        super().__init__("product-service", f"Product {product_id} not found", 404)


class InsufficientStockError(MicroserviceError):
    def __init__(self, product_id: str, available: int, requested: int):
        super().__init__(
            "product-service",
            f"Insufficient stock for product {product_id}: {available} available, {requested} requested",
            409,
        )
