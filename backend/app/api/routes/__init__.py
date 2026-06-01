"""API router registry."""

from fastapi import APIRouter

from app.api.routes.system import router as system_router

api_router = APIRouter()
api_router.include_router(system_router, prefix="/system", tags=["system"])
