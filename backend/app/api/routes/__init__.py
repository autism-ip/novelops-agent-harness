"""API router registry."""

from fastapi import APIRouter

from app.api.routes.pipelines import router as pipelines_router
from app.api.routes.system import router as system_router
from app.api.routes.workflows import router as workflows_router
from app.api.routes.observability import router as observability_router
from app.api.routes.hotspots import router as hotspots_router
from app.api.routes.research import router as research_router
from app.api.routes.creative import router as creative_router
from app.api.routes.books import router as books_router
from app.api.routes.story_planning import router as story_planning_router

api_router = APIRouter()
api_router.include_router(system_router, prefix="/system", tags=["system"])
api_router.include_router(pipelines_router, prefix="/pipelines", tags=["pipelines"])
api_router.include_router(workflows_router, prefix="/workflows", tags=["workflows"])
api_router.include_router(observability_router, tags=["observability"])
api_router.include_router(hotspots_router, prefix="/hotspots", tags=["hotspots"])
api_router.include_router(research_router, tags=["research"])
api_router.include_router(creative_router, tags=["creative"])
api_router.include_router(books_router, prefix="/books", tags=["books"])
api_router.include_router(story_planning_router, tags=["story-planning"])
