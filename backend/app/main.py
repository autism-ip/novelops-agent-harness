"""NovelOps Agent Harness — FastAPI Entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import APIKeyMiddleware
from app.api.routes import api_router
from app.config import Settings
from app.constants import APP_TITLE, APP_VERSION


def create_app(settings: Settings) -> FastAPI:
    """Application factory — accepts Settings, returns configured FastAPI."""
    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        description="AI-assisted web-novel production system",
    )

    app.state.settings = settings
    settings.app_version = APP_VERSION

    # APIKeyMiddleware added first → innermost (runs last).
    # CORSMiddleware added last → outermost (runs first, handles preflight).
    app.add_middleware(APIKeyMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api")

    return app


# Lazy module-level app: only created when `app` is actually accessed.
# This prevents Settings() from running at import time (which would fail
# if BACKEND_API_KEY is not set in the environment).
def __getattr__(name: str):
    if name == "app":
        return create_app(Settings())
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
