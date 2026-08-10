# TODO Card 5 — Criar Producer API
from fastapi import FastAPI

app = FastAPI(title="Producer API")

@app.get("/health")
def health():
    return {"status": "ok"}
