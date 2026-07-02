from fastapi import FastAPI
from app.database import test_connection

app = FastAPI()

@app.get("/")
async def root():
    connected, result = await test_connection()
    if connected:
        return {
            "message": "Backend running",
            "database": "connected",
            "postgres_version": result
        }
    else:
        return {
            "message": "Backend running",
            "database": "disconnected",
            "error": result
        }