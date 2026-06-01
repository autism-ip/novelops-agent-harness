"""FastAPI dependency injection helpers."""

from fastapi import Request

from app.config import Settings


def get_settings(request: Request) -> Settings:
    """Retrieve Settings from app.state."""
    return request.app.state.settings
