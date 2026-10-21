"""API router registry."""

from fastapi import APIRouter

from app.api.routes.pipelines import router as pipelines_router
from app.api.routes.system import router as system_router
from app.api.routes.workflows import router as workflows_router

api_router = APIRouter()
api_router.include_router(system_router, prefix="/system", tags=["system"])
api_router.include_router(pipelines_router, prefix="/pipelines", tags=["pipelines"])
api_router.include_router(workflows_router, prefix="/workflows", tags=["workflows"])
