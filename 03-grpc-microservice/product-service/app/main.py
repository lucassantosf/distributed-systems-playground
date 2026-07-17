from fastapi import FastAPI

app = FastAPI(title="Product Service")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "product-service"}
