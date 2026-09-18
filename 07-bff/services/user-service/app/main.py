from fastapi import FastAPI

from app.routers import users

app = FastAPI(title="User Service", version="0.1.0")

app.include_router(users.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "user-service"}
