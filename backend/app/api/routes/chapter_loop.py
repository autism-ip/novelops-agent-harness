"""Exact-source chapter generation, version history and final-lock API."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.routes.workflows import get_kernel
from app.chapter_loop import ChapterRequest

router = APIRouter()


def service(kernel=Depends(get_kernel)):
    chapter = getattr(kernel, "chapter_loop", None)
    if chapter is None:
        raise HTTPException(503, "Chapter loop is not configured")
    return chapter


class FinalLock(BaseModel):
    version_id: str = Field(min_length=1, max_length=200)
    artifact_id: str = Field(min_length=1, max_length=200)
    version_no: int = Field(ge=1, strict=True)
    operator: str = Field(min_length=1, max_length=100)


@router.get("/books/{book_id}/chapters/{chapter_no}/generation/context")
def context(book_id: str, chapter_no: int, chapter=Depends(service)):
    return chapter.context(book_id, chapter_no)


@router.post("/books/{book_id}/chapters/{chapter_no}/generations", status_code=201)
def create(book_id: str, chapter_no: int, body: ChapterRequest, chapter=Depends(service)):
    if body.book_id != book_id or body.chapter_no != chapter_no:
        raise HTTPException(422, "Book or chapter mismatch")
    return chapter.enqueue(body.model_dump())


@router.get("/books/{book_id}/chapters/{chapter_no}/generations")
def list_runs(book_id: str, chapter_no: int, chapter=Depends(service)):
    return chapter.list_runs(book_id, chapter_no)


@router.get("/books/{book_id}/chapters/{chapter_no}/versions")
def versions(book_id: str, chapter_no: int, chapter=Depends(service)):
    return chapter.versions(book_id, chapter_no)


@router.get("/chapter-generations/{run_id}")
def read(run_id: str, chapter=Depends(service)):
    return chapter.read(run_id)


@router.post("/books/{book_id}/chapters/{chapter_no}/final-lock")
def lock_final(book_id: str, chapter_no: int, body: FinalLock, chapter=Depends(service)):
    return chapter.lock_final(book_id, chapter_no, **body.model_dump())
