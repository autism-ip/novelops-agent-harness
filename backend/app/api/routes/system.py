"""System endpoints — health, status, config."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    """Liveness probe — public, no auth required."""
    settings = request.app.state.settings
    return {"status": "ok", "version": settings.app_version}


@router.get("/status")
async def status():
    """Readiness probe — component placeholders, public."""
    return {
        "backend_status": "running",
        "worker_status": "not_started",
        "feishu_status": "not_configured",
        "opencli_status": "not_configured",
        "active_pipeline_runs": 0,
        "pending_steps": 0,
        "failed_steps": 0,
    }


@router.get("/config")
async def config(request: Request):
    """Protected config — requires valid API key."""
    settings = request.app.state.settings
    return {
        "llm_provider": settings.llm_provider,
        "opencli_enabled": settings.opencli_enabled,
        "cors_origins": settings.cors_origins,
    }
