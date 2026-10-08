from fastapi import FastAPI

app = FastAPI(title="Saga Orchestrator", version="0.1.0")

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "orchestrator"}

