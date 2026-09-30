"""Authenticated v0.2 workflow control/read contract."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.harness import HarnessKernel

router = APIRouter()


def get_kernel(request: Request) -> HarnessKernel:
    kernel = getattr(request.app.state, "kernel", None)
    if kernel is None:
        raise HTTPException(503, "Harness is not configured")
    return kernel


class StepBody(BaseModel):
    step_key: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    handler: str = Field(min_length=1)
    kind: Literal["tool", "service", "agent"] = "service"
    depends_on: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    input: dict = Field(default_factory=dict)


class WorkflowBody(BaseModel):
    request_key: str = Field(min_length=1, max_length=200)
    workflow_type: str = Field(min_length=1, max_length=128)
    steps: list[StepBody] = Field(min_length=1, max_length=100)
    book_id: str = ""
    source_hotspot_id: str = ""


class DecisionBody(BaseModel):
    action: Literal["approve", "reject", "revise"]
    expected_version: int = Field(ge=1)
    operator: str = Field(min_length=1)
    reason: str = Field(default="", max_length=4000)


@router.post("", status_code=201)
def create(body: WorkflowBody, kernel=Depends(get_kernel)):
    if (body.request_key.startswith(("research:", "creative:", "story-planning:", "chapter-loop:")) or
        body.workflow_type.startswith(("hotspot_research", "title_candidates", "cover_plans",
                                       "story_bible", "chapter_brief", "chapter_loop")) or
        any(s.handler.startswith(("research.", "titles.", "covers.", "story_bible.", "chapter_brief.", "chapter."))
            for s in body.steps)):
        raise HTTPException(422, "Use the versioned domain endpoint for research, creative, story or chapter workflows")
    return kernel.create(body.request_key, body.workflow_type,
                         [s.model_dump() for s in body.steps],
                         book_id=body.book_id, source_hotspot_id=body.source_hotspot_id)


@router.get("")
def list_runs(kernel=Depends(get_kernel)):
    return kernel.list()


@router.get("/{run_id}")
def get(run_id: str, kernel=Depends(get_kernel)):
    return kernel.get(run_id)


@router.post("/{run_id}/cancel")
def cancel(run_id: str, kernel=Depends(get_kernel)):
    return kernel.cancel(run_id)


@router.post("/steps/{step_id}/decision")
def decision(step_id: str, body: DecisionBody, kernel=Depends(get_kernel)):
    return kernel.decide(step_id, body.action, body.expected_version, body.operator, reason=body.reason)
