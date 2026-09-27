"""Authenticated version reservations, analysis reads and exact-gate decisions."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ConfigDict, Field

from app.api.routes.workflows import DecisionBody, get_kernel
from app.research import AnalysisRequest, Strict
from app.harness import TransitionConflict
from app.storage import MissingRecord

router = APIRouter()


def service(kernel=Depends(get_kernel)):
    research = getattr(kernel, "research", None)
    if research is None:
        raise HTTPException(503, "Opportunity research is not configured")
    return research


class Batch(Strict):
    request_key: str = Field(min_length=1, max_length=200)
    items: list[AnalysisRequest] = Field(min_length=1, max_length=20)


class AnalysisDecision(DecisionBody):
    model_config = ConfigDict(extra="forbid")
    artifact_id: str = Field(min_length=1, max_length=200)
    step_id: str = Field(min_length=1, max_length=200)


@router.get("/hotspots/{hotspot_id}/research-context")
def context(hotspot_id: str, research=Depends(service)):
    return research.context(hotspot_id)


@router.get("/hotspots/{hotspot_id}/analyses")
def list_analyses(hotspot_id: str, research=Depends(service)):
    with research.kernel.writer:
        return [research.get(run["pipeline_run_id"]) for run in reversed(research.runs(hotspot_id))]


@router.post("/analyses", status_code=201)
def enqueue(body: Batch, research=Depends(service)):
    # Each explicit hotspot/version is an idempotent reservation. A partial
    # transport failure can be retried with the exact same manifest.
    if len({item.hotspot_id for item in body.items}) != len(body.items):
        raise ValueError("Batch must contain distinct hotspots")
    runs, errors = [], []
    for item in body.items:
        try:
            runs.append(research.enqueue(item.model_dump()))
        except (TransitionConflict, MissingRecord) as exc:
            errors.append({"hotspot_id": item.hotspot_id, "detail": str(exc) if isinstance(exc, TransitionConflict) else "Hotspot not found"})
    return {"runs": runs, "errors": errors}


@router.get("/analyses/{run_id}")
def get(run_id: str, research=Depends(service)):
    return research.get(run_id)


@router.get("/analyses/{run_id}/approved")
def approved(run_id: str, research=Depends(service)):
    return research.approved(run_id)


@router.post("/analyses/{run_id}/decision")
def decide(run_id: str, body: AnalysisDecision, research=Depends(service)):
    return research.decide(run_id, **body.model_dump())
