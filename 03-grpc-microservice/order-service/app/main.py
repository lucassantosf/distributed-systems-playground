from fastapi import FastAPI

app = FastAPI(title="Order Service")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "order-service"}
