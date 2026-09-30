"""Exact selected-source bootstrap and canonical book state reads."""
from fastapi import APIRouter, Depends, HTTPException

from app.api.routes.workflows import get_kernel
from app.books import BootstrapRequest

router = APIRouter()


def service(kernel=Depends(get_kernel)):
    books = getattr(kernel, "books", None)
    if books is None:
        raise HTTPException(503, "Book bootstrap is not configured")
    return books


@router.get("")
def list_books(books=Depends(service)):
    return books.list_books()


@router.get("/bootstrap-context/{cover_run_id}")
def bootstrap_context(cover_run_id: str, books=Depends(service)):
    return books.context(cover_run_id)


@router.post("", status_code=201)
def bootstrap(body: BootstrapRequest, books=Depends(service)):
    return books.bootstrap(body.model_dump())


@router.get("/{book_id}")
def get_book(book_id: str, books=Depends(service)):
    return books.read(book_id)


@router.get("/{book_id}/story-state")
def get_story_state(book_id: str, books=Depends(service)):
    return books.context_provider.get(book_id)["state"]
