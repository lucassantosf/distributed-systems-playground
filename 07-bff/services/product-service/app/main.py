from fastapi import FastAPI

app = FastAPI(title="Product Service", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "product-service"}
