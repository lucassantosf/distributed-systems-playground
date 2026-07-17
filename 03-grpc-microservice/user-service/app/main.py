from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from routers.user import router as user_router

app = FastAPI(title="User Service")

app.include_router(user_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = {}
    for error in exc.errors():
        loc = error["loc"]
        if len(loc) > 1:
            field = loc[-1]
        else:
            field = loc[0]
        errors[field] = error["msg"]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "user-service"}
