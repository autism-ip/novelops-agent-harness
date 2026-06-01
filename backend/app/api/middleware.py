"""API key guard middleware."""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Reject requests without a valid X-API-Key header.

    Public endpoints bypass this guard via path allowlist.
    """

    PUBLIC_PATHS = frozenset({
        "/api/system/health",
        "/api/system/status",
    })

    async def dispatch(self, request: Request, call_next):
        # Only guard /api routes; let /docs, /openapi.json, etc. pass through.
        if not request.url.path.startswith("/api"):
            return await call_next(request)

        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        settings = request.app.state.settings
        key = request.headers.get("x-api-key", "")
        if key != settings.backend_api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
