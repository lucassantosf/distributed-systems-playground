from fastapi import FastAPI
from sqlalchemy import text

from database import SessionLocal, init_db

app = FastAPI(title="Command API")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
async def health():
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        db_ok = False

    return {"status": "ok" if db_ok else "degraded", "database": "healthy" if db_ok else "unhealthy"}
