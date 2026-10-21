"""Exact-version StoryBible approvals and policy-eligible ChapterBrief APIs."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from app.api.routes.workflows import DecisionBody, get_kernel
from app.story_planning import BibleRequest, BriefRequest

router = APIRouter()


def service(kernel=Depends(get_kernel)):
    planning = getattr(kernel, "story_planning", None)
    if planning is None:
        raise HTTPException(503, "Story planning is not configured")
    return planning


class BibleDecision(DecisionBody):
    step_id: str = Field(min_length=1, max_length=200)
    artifact_id: str = Field(default="", max_length=200)
    action: Literal["approve", "reject", "revise"]


@router.get("/books/{book_id}/bible/context")
def bible_context(book_id: str, planning=Depends(service)):
    return planning.bible_context(book_id)


@router.post("/books/{book_id}/bibles", status_code=201)
def create_bible(book_id: str, body: BibleRequest, planning=Depends(service)):
    if body.book_id != book_id:
        raise HTTPException(422, "Book ID mismatch")
    return planning.enqueue_bible(body.model_dump())


@router.get("/books/{book_id}/bibles")
def list_bibles(book_id: str, planning=Depends(service)):
    return planning.list_bibles(book_id)


@router.get("/books/{book_id}/chapters/{chapter_no}/brief/context")
def brief_context(book_id: str, chapter_no: int, planning=Depends(service)):
    return planning.brief_context(book_id, chapter_no)


@router.post("/books/{book_id}/chapters/{chapter_no}/briefs", status_code=201)
def create_brief(book_id: str, chapter_no: int, body: BriefRequest, planning=Depends(service)):
    if body.book_id != book_id or body.chapter_no != chapter_no:
        raise HTTPException(422, "Book or chapter mismatch")
    return planning.enqueue_brief(body.model_dump())


@router.get("/books/{book_id}/chapters/{chapter_no}/briefs")
def list_briefs(book_id: str, chapter_no: int, planning=Depends(service)):
    return planning.list_briefs(book_id, chapter_no)


@router.get("/books/{book_id}/chapters/{chapter_no}/brief/eligible")
def eligible_brief(book_id: str, chapter_no: int, planning=Depends(service)):
    return planning.eligible_brief(book_id, chapter_no)


@router.get("/story-planning/runs/{run_id}")
def read_run(run_id: str, planning=Depends(service)):
    return planning.read(run_id)


@router.post("/story-planning/runs/{run_id}/decision")
def decide_bible(run_id: str, body: BibleDecision, planning=Depends(service)):
    return planning.decide_bible(run_id, **body.model_dump())
