"""Authenticated hotspot reads, collection and durable manual controls."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.api.routes.workflows import get_kernel
from app.hotspot_controls import ManualInput

router = APIRouter()


def service(kernel=Depends(get_kernel)):
    result = getattr(kernel, "hotspots", None)
    if result is None:
        raise HTTPException(503, "Hotspot ingestion is not configured")
    return result


class FetchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=50, ge=30, le=50)


class ManualBody(ManualInput):
    request_key: str = Field(min_length=1, max_length=200, pattern=r"\S")


class DiscardBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(min_length=1, max_length=200, pattern=r"\S")
    expected_status: Literal["new", "normalized", "analyzed", "approved", "discarded"]


@router.get("/capabilities")
def capabilities(hotspots=Depends(service)):
    return {"fetch": hotspots.collection_enabled, "manual_add": True, "discard": True,
            "analyze": getattr(hotspots.kernel, "research", None) is not None,
            "creative": getattr(hotspots.kernel, "creative", None) is not None}


@router.post("/manual", status_code=201)
def manual(body: ManualBody, hotspots=Depends(service)):
    return hotspots.controls.enqueue_add(body.request_key, body.model_dump(exclude={"request_key"}))


@router.post("/{hotspot_id}/discard", status_code=201)
def discard(hotspot_id: str, body: DiscardBody, hotspots=Depends(service)):
    return hotspots.controls.enqueue_discard(hotspot_id, body.request_key, body.expected_status)


@router.post("/fetch", status_code=201)
def fetch(body: FetchBody, hotspots=Depends(service)):
    if not hotspots.collection_enabled:
        raise HTTPException(503, "Hotspot collection is disabled")
    return hotspots.enqueue(body.request_key, body.limit)


@router.get("")
def list_hotspots(source: Literal["douyin", "manual"] | None = None,
                  status: Literal["new", "normalized", "analyzed", "approved", "discarded"] | None = None,
                  captured_from: AwareDatetime | None = None, captured_to: AwareDatetime | None = None,
                  offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                  hotspots=Depends(service)):
    return hotspots.list(source=source, status=status, captured_from=captured_from,
                         captured_to=captured_to, offset=offset, limit=limit)


@router.get("/{hotspot_id}")
def get_hotspot(hotspot_id: str, hotspots=Depends(service)):
    return hotspots.get(hotspot_id)
