"""API routes package."""

from fastapi import APIRouter
from .resume import router as resume_router
from .tailor import router as tailor_router

api_router = APIRouter()

# Include sub-routers
api_router.include_router(resume_router)
api_router.include_router(tailor_router)

@api_router.get("/health", summary="Health check", tags=["Monitoring"])
async def health_check():
    """
    Checks the health of the API.
    Returns:
        dict: A dictionary with status "ok".
    """
    return {"status": "ok"}
