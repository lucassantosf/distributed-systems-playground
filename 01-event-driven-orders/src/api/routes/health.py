from fastapi import APIRouter

from src.settings import settings

router = APIRouter()

@router.get("/health", status_code=200)
def health_check():
    return {"status": "ok", "service": settings.PROJECT_NAME}
