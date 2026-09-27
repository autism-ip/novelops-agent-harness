"""Protected artifact/trace/usage APIs; credentials and raw prompts excluded."""
from fastapi import APIRouter, Depends, HTTPException

from app.api.routes.workflows import get_kernel
from app.generation import ArtifactIntegrityError

router = APIRouter()


def enabled(kernel):
    if not kernel.telemetry:
        raise HTTPException(503, "Generation telemetry is not configured")
    return kernel.telemetry


@router.get("/workflows/{run_id}/trace")
def run_trace(run_id: str, kernel=Depends(get_kernel)):
    kernel.get(run_id)
    return enabled(kernel).list(run_id=run_id)


@router.get("/workflows/{run_id}/usage")
def run_usage(run_id: str, kernel=Depends(get_kernel)):
    kernel.get(run_id)
    return enabled(kernel).usage(run_id=run_id)


@router.get("/chapters/{chapter_id}/usage")
def chapter_usage(chapter_id: str, kernel=Depends(get_kernel)):
    return enabled(kernel).usage(chapter_id=chapter_id)


@router.get("/artifacts/{artifact_id}")
def artifact(artifact_id: str, kernel=Depends(get_kernel)):
    if not getattr(kernel, "artifacts", None):
        raise HTTPException(503, "Artifact storage is not configured")
    try:
        return kernel.artifacts.get(artifact_id)
    except ArtifactIntegrityError:
        raise HTTPException(409, "Artifact integrity check failed; reconciliation required") from None
