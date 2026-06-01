"""Health and status endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    """Liveness probe — returns 200 when process is alive."""
    return {"status": "ok"}


@router.get("/status")
async def status():
    """Readiness probe — returns version and runtime info."""
    return {
        "version": "0.1.0",
        "status": "running",
    }
