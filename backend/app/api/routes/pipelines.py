"""
[INPUT]: 依赖 FastAPI 的 APIRouter/Depends/HTTPException，依赖 Pydantic 的 BaseModel，
         依赖 app.state.settings、app.feishu.client.FeishuClient、contextlib，
         app.feishu.repositories.pipeline_runs.PipelineRunsRepo、
         app.feishu.repositories.step_runs.StepRunsRepo、
         app.feishu.table_map.TableMapConfig、
         app.pipeline.engine.PipelineEngine、app.pipeline.models.StepDef
[OUTPUT]: 对外提供 router（POST /pipelines、GET /pipelines/{id}、GET /pipelines/{id}/steps）
[POS]: api.routes 包的兼容管线端点；使用应用配置并在请求结束/异常时关闭客户端，保持 v0.2 创建禁用与安全业务键查询
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.config import Settings
from app.feishu.client import FeishuClient
from app.feishu.repositories.pipeline_runs import PipelineRunsRepo
from app.feishu.repositories.step_runs import StepRunsRepo
from app.feishu.table_map import TableMapConfig
from app.pipeline.engine import PipelineEngine
from app.pipeline.models import StepDef
from app.storage import DuplicateKey

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


def _get_client(settings: Settings) -> FeishuClient:
    """Build FeishuClient from settings."""
    return FeishuClient(settings.FEISHU_APP_ID, settings.FEISHU_APP_SECRET)


def _get_config(settings: Settings) -> TableMapConfig:
    """Use this app's resolved settings, including dotenv and explicit overrides."""
    return TableMapConfig(app_token=settings.FEISHU_APP_TOKEN, table_ids={
        name: getattr(settings, "FEISHU_TABLE_ID_" + name.upper())
        for name in ("pipeline_runs", "step_runs")
    })


@contextmanager
def _client_context(settings: Settings) -> Iterator[tuple[FeishuClient, TableMapConfig]]:
    """Own one request's client through setup, repository IO and error handling."""
    client = _get_client(settings)
    try:
        yield client, _get_config(settings)
    finally:
        client._http.close()


def _build_pipeline_repo(client: FeishuClient, config: TableMapConfig) -> PipelineRunsRepo:
    """Construct PipelineRunsRepo with shared client."""
    return PipelineRunsRepo(
        client, config.app_token, config.get_table_id("pipeline_runs")
    )


def _build_step_repo(client: FeishuClient, config: TableMapConfig) -> StepRunsRepo:
    """Construct StepRunsRepo with shared client."""
    return StepRunsRepo(
        client, config.app_token, config.get_table_id("step_runs")
    )


def get_engine(request: Request) -> Iterator[PipelineEngine]:
    """Keep real repos available until the endpoint finishes, then release IO."""
    if getattr(request.app.state, "kernel", None) is not None:
        raise HTTPException(410, "Use /api/workflows for v0.2 execution")
    with _client_context(request.app.state.settings) as (client, config):
        yield PipelineEngine(_build_pipeline_repo(client, config), _build_step_repo(client, config))


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

    try:
        result = engine.create_pipeline(
            pipeline_type=body.pipeline_type,
            step_defs=step_defs,
            source_hotspot_id=body.source_hotspot_id,
            book_id=body.book_id,
            operator=body.operator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"pipeline_run_id": result["pipeline_run_id"], "status": result["status"]}


@router.get("/{pipeline_run_id}")
async def get_pipeline(
    pipeline_run_id: str,
    request: Request,
) -> dict:
    """Get a pipeline run with its step runs included.

    Returns 404 if pipeline_run_id does not exist.
    """
    with _client_context(request.app.state.settings) as (client, config):
        pipeline_repo = _build_pipeline_repo(client, config)
        step_repo = _build_step_repo(client, config)

        try:
            pipeline = pipeline_repo.find_by_business_key(pipeline_run_id=pipeline_run_id)
        except DuplicateKey as exc:
            raise HTTPException(status_code=409, detail="Duplicate pipeline run ID") from exc
        if pipeline is None:
            raise HTTPException(status_code=404, detail="Pipeline run not found")

        pipeline["step_runs"] = step_repo.find_by_pipeline(pipeline_run_id)
        return pipeline


@router.get("/{pipeline_run_id}/steps")
async def list_step_runs(
    pipeline_run_id: str,
    request: Request,
) -> list[dict]:
    """List all step runs belonging to a pipeline run."""
    with _client_context(request.app.state.settings) as (client, config):
        step_repo = _build_step_repo(client, config)
        return step_repo.find_by_pipeline(pipeline_run_id)
