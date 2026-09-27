"""NovelOps Agent Harness — FastAPI Entrypoint."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from app.api.middleware import APIKeyMiddleware
from app.api.routes import api_router
from app.config import Settings
from app.constants import APP_TITLE, APP_VERSION


def create_app(settings: Settings, *, kernel=None) -> FastAPI:
    """Application factory — accepts Settings, returns configured FastAPI."""
    @asynccontextmanager
    async def lifespan(app):
        from app.runtime import build_runtime
        runtime = kernel
        client = None
        try:
            if runtime is None and settings.HARNESS_ENABLED:
                runtime, client = build_runtime(settings)
            app.state.kernel = runtime
            if runtime:
                await asyncio.to_thread(runtime.start)
            yield
        finally:
            if runtime:
                await asyncio.to_thread(runtime.stop)
            if client:
                client._http.close()

    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        description="AI-assisted web-novel production system",
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.kernel = kernel
    settings.APP_VERSION = APP_VERSION

    # APIKeyMiddleware added first → innermost (runs last).
    # CORSMiddleware added last → outermost (runs first, handles preflight).
    app.add_middleware(APIKeyMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api")

    from app.harness import TransitionConflict
    from app.storage import StorageError, MissingRecord
    from app.feishu.client import FeishuError

    @app.exception_handler(TransitionConflict)
    async def conflict(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(MissingRecord)
    async def missing(request, exc):
        return JSONResponse(status_code=404, content={"detail": "Record not found"})

    @app.exception_handler(StorageError)
    @app.exception_handler(FeishuError)
    async def storage_error(request, exc):
        return JSONResponse(status_code=503, content={"detail": type(exc).__name__, "reconciliation_required": True})

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    return app


# Lazy module-level app: only created when `app` is actually accessed.
# This prevents Settings() from running at import time (which would fail
# if BACKEND_API_KEY is not set in the environment).
def __getattr__(name: str):
    if name == "app":
        return create_app(Settings())
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
