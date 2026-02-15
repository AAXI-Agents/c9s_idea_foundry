"""Health check router."""

from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description="Returns a simple ok payload to confirm the service is running.",
)
async def health():
    """Basic liveness probe."""
    return {"status": "ok"}
