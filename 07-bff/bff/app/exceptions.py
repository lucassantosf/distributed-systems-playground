from fastapi import Request
from fastapi.responses import JSONResponse


class BFFException(Exception):
    def __init__(self, status_code: int, error: str, service: str, type: str):
        self.status_code = status_code
        self.error = error
        self.service = service
        self.type = type


async def bff_exception_handler(request: Request, exc: BFFException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error,
            "service": exc.service,
            "type": exc.type,
        },
    )

