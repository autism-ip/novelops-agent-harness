"""Exact-source title/cover generation and choice contracts."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from app.api.routes.workflows import DecisionBody, get_kernel
from app.creative import CreativeRequest

router = APIRouter()


def service(kernel=Depends(get_kernel)):
    creative = getattr(kernel, "creative", None)
    if creative is None:
        raise HTTPException(503, "Title and cover planning is not configured")
    return creative


class Decision(DecisionBody):
    step_id: str = Field(min_length=1, max_length=200)
    artifact_id: str = Field(default="", max_length=200)


@router.get("/creative/{kind}/{source_run_id}/context")
def context(kind: Literal["titles", "covers"], source_run_id: str, creative=Depends(service)):
    return creative.context(kind, source_run_id)


@router.get("/creative/{kind}/{source_run_id}/runs")
def runs(kind: Literal["titles", "covers"], source_run_id: str, creative=Depends(service)):
    return [creative.read(row["pipeline_run_id"]) for row in reversed(creative.list_runs(kind, source_run_id))]


@router.post("/creative/{kind}", status_code=201)
def enqueue(kind: Literal["titles", "covers"], body: CreativeRequest, creative=Depends(service)):
    return creative.enqueue(kind, body.model_dump())


@router.get("/creative/runs/{run_id}")
def read(run_id: str, creative=Depends(service)):
    return creative.read(run_id)


@router.post("/creative/runs/{run_id}/decision")
def decide(run_id: str, body: Decision, creative=Depends(service)):
    return creative.decide(run_id, **body.model_dump())


@router.get("/creative/runs/{run_id}/selected")
def selected(run_id: str, creative=Depends(service)):
    state = creative.read(run_id)
    return creative.selected(state["kind"], run_id)
