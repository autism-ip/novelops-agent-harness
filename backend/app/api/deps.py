"""API key guard middleware."""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Reject requests without a valid X-API-Key header.

    Skipped when BACKEND_API_KEY is empty (dev mode).
    """

    async def dispatch(self, request: Request, call_next):
        if not settings.BACKEND_API_KEY:
            return await call_next(request)

        key = request.headers.get("x-api-key", "")
        if key != settings.BACKEND_API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
