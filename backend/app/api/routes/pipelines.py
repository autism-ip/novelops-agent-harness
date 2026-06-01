"""
[INPUT]: 依赖 FastAPI 的 APIRouter/Depends/HTTPException，依赖 Pydantic 的 BaseModel，
         依赖 app.config.settings、app.feishu.client.FeishuClient、
         app.feishu.repositories.pipeline_runs.PipelineRunsRepo、
         app.feishu.repositories.step_runs.StepRunsRepo、
         app.feishu.table_map.TableMapConfig、
         app.pipeline.engine.PipelineEngine、app.pipeline.models.StepDef
[OUTPUT]: 对外提供 router（POST /pipelines、GET /pipelines/{id}、GET /pipelines/{id}/steps）
[POS]: api.routes 包的管线端点模块，封装 PipelineEngine 生命周期，被 routes/__init__.py 注册到 api_router
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.feishu.client import FeishuClient
from app.feishu.repositories.pipeline_runs import PipelineRunsRepo
from app.feishu.repositories.step_runs import StepRunsRepo
from app.feishu.table_map import TableMapConfig
from app.pipeline.engine import PipelineEngine
from app.pipeline.models import StepDef

router = APIRouter()


# ============================================================
# request bodies
# ============================================================


class StepDefBody(BaseModel):
    """Single step in a pipeline creation request."""

    step_key: str
    assigned_agent_id: str
    depends_on: list[str] = []


class CreatePipelineBody(BaseModel):
    """Request body for POST /pipelines."""

    pipeline_type: str
    steps: list[StepDefBody]
    source_hotspot_id: str = ""
    book_id: str = ""
    operator: str = ""


# ============================================================
# dependency wiring
# ============================================================


@lru_cache(maxsize=1)
def _get_client() -> FeishuClient:
    """Singleton Feishu client — reuses token cache across requests."""
    return FeishuClient(settings.FEISHU_APP_ID, settings.FEISHU_APP_SECRET)


@lru_cache(maxsize=1)
def _get_config() -> TableMapConfig:
    """Singleton table-map config — reads FEISHU_APP_TOKEN from env."""
    return TableMapConfig()


def _build_pipeline_repo() -> PipelineRunsRepo:
    """Construct PipelineRunsRepo with shared client."""
    client = _get_client()
    config = _get_config()
    return PipelineRunsRepo(
        client, config.app_token, config.get_table_id("pipeline_runs")
    )


def _build_step_repo() -> StepRunsRepo:
    """Construct StepRunsRepo with shared client."""
    client = _get_client()
    config = _get_config()
    return StepRunsRepo(
        client, config.app_token, config.get_table_id("step_runs")
    )


def get_engine() -> PipelineEngine:
    """FastAPI dependency — returns a PipelineEngine with real repos."""
    return PipelineEngine(_build_pipeline_repo(), _build_step_repo())


# ============================================================
# endpoints
# ============================================================


@router.post("", status_code=201)
async def create_pipeline(
    body: CreatePipelineBody,
    engine: PipelineEngine = Depends(get_engine),
) -> dict:
    """Create a pipeline run with step definitions.

    Returns 201 with pipeline_run_id and initial status.
    """
    step_defs = [
        StepDef(
            step_key=s.step_key,
            assigned_agent_id=s.assigned_agent_id,
            depends_on=tuple(s.depends_on),
        )
        for s in body.steps
    ]

    result = engine.create_pipeline(
        pipeline_type=body.pipeline_type,
        step_defs=step_defs,
        source_hotspot_id=body.source_hotspot_id,
        book_id=body.book_id,
        operator=body.operator,
    )

    return {"pipeline_run_id": result["pipeline_run_id"], "status": result["status"]}


@router.get("/{pipeline_run_id}")
async def get_pipeline(
    pipeline_run_id: str,
    engine: PipelineEngine = Depends(get_engine),
) -> dict:
    """Get a pipeline run with its step runs included.

    Returns 404 if pipeline_run_id does not exist.
    """
    pipeline_repo = _build_pipeline_repo()
    step_repo = _build_step_repo()

    runs = pipeline_repo.list(
        filter_expr=f'CurrentValue.[pipeline_run_id] = "{pipeline_run_id}"'
    )
    if not runs:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    pipeline = runs[0]
    pipeline["step_runs"] = step_repo.find_by_pipeline(pipeline_run_id)
    return pipeline


@router.get("/{pipeline_run_id}/steps")
async def list_step_runs(
    pipeline_run_id: str,
    engine: PipelineEngine = Depends(get_engine),
) -> list[dict]:
    """List all step runs belonging to a pipeline run."""
    step_repo = _build_step_repo()
    return step_repo.find_by_pipeline(pipeline_run_id)
