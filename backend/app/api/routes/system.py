"""System endpoints — health, status, config."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    """Liveness probe — public, no auth required."""
    settings = request.app.state.settings
    return {"status": "ok", "version": settings.APP_VERSION}


@router.get("/status")
def status(request: Request):
    """Readiness probe — component placeholders, public."""
    result = {
        "backend_status": "running",
        "worker_status": "not_started",
        "feishu_status": "not_configured",
        "opencli_status": "not_configured",
        "active_pipeline_runs": 0,
        "pending_steps": 0,
        "failed_steps": 0,
    }
    kernel = getattr(request.app.state, "kernel", None)
    if kernel is not None:
        try:
            result.update(kernel.status())
        except Exception:
            result.update(worker_status="running" if kernel.running else "stopped", feishu_status="unreachable")
    return result


@router.get("/config")
async def config(request: Request):
    """Protected config — requires valid API key."""
    settings = request.app.state.settings
    return {
        "llm_provider": settings.LLM_PROVIDER,
        "opencli_enabled": settings.OPENCLI_ENABLED,
        "cors_origins": settings.CORS_ORIGINS,
    }
