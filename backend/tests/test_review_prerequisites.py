"""The desk must fail safely when prerequisites are unavailable or target IDs drift."""
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.harness import HarnessKernel
from app.main import create_app
from tests.feishu_transport import make_storage
from tests.test_chapter_review import chapter as chapter

pytest_plugins = ("tests.test_story_planning",)


@pytest.mark.parametrize("path,detail", [
    ("/api/hotspots", "Hotspot ingestion is not configured"),
    ("/api/analyses/unconfigured", "Opportunity research is not configured"),
    ("/api/creative/runs/unconfigured", "Title and cover planning is not configured"),
    ("/api/books", "Book bootstrap is not configured"),
    ("/api/books/unconfigured/bibles", "Story planning is not configured"),
    ("/api/books/unconfigured/chapters/1/review", "Chapter loop is not configured"),
])
def test_missing_desk_prerequisite_is_authenticated_and_side_effect_free(tmp_path, path, detail):
    storage, transport, client = make_storage()
    kernel = HarnessKernel(storage, journal_dir=tmp_path)
    api = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    try:
        denied = api.get(path)
        assert denied.status_code == 401
        assert denied.json() == {"detail": "Invalid or missing API key"}
        unavailable = api.get(path, headers={"x-api-key": "test"})
        assert unavailable.status_code == 503
        assert unavailable.json() == {"detail": detail}
        assert transport.calls == []
        assert not kernel.running
        assert api.get("/api/system/health").json()["status"] == "ok"
        assert transport.calls == []
    finally:
        api.close()
        kernel.stop()
        client._http.close()


@pytest.mark.parametrize("kind,changed", [
    ("bible", "book_id"), ("brief", "book_id"), ("brief", "chapter_no"),
    ("chapter", "book_id"), ("chapter", "chapter_no"),
])
def test_authorized_generation_cannot_cross_its_url_target(chapter, kind, changed):
    kernel, provider, book_id = chapter
    if kind == "bible":
        body = kernel.story_planning.bible_context(book_id)
        path = f"/api/books/{book_id}/bibles"
        detail = "Book ID mismatch"
    elif kind == "brief":
        body = kernel.story_planning.brief_context(book_id, 1)
        path = f"/api/books/{book_id}/chapters/1/briefs"
        detail = "Book or chapter mismatch"
    else:
        body = kernel.chapter_loop.context(book_id, 1)
        path = f"/api/books/{book_id}/chapters/1/generations"
        detail = "Book or chapter mismatch"
    body = {**body, changed: "another-book" if changed == "book_id" else 2}
    transport = kernel.storage._repos["artifacts"]._client._http._transport.handler
    offset, model_calls = len(transport.calls), list(provider.calls)
    api = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    try:
        result = api.post(path, headers={"x-api-key": "test"}, json=body)
        assert result.status_code == 422, result.text
        assert result.json() == {"detail": detail}
        assert transport.calls[offset:] == []
        assert provider.calls == model_calls
    finally:
        api.close()
