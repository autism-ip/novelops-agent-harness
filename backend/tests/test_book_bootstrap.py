"""ZEN-38: exact source selection, one canonical state, and interrupted recovery."""
import pytest
from fastapi.testclient import TestClient

from app.books import BookService, StoryStateContent
from app.config import Settings
from app.harness import TransitionConflict
from app.main import create_app
from app.runtime import build_runtime
from app.storage import AmbiguousWrite
from tests.test_creative_workflow import choose, enqueue, settle

pytest_plugins = ("tests.test_creative_workflow",)


def test_books_fail_fast_without_creative_runtime():
    with pytest.raises(ValueError, match="BOOKS_ENABLED requires CREATIVE_ENABLED"):
        build_runtime(Settings(_env_file=None, BACKEND_API_KEY="test", BOOKS_ENABLED=True))


def selected_cover(kernel, analysis_run):
    title_run = enqueue(kernel, "titles", analysis_run)
    settle(kernel)
    choose(kernel, title_run["pipeline_run_id"])
    cover_run = enqueue(kernel, "covers", title_run["pipeline_run_id"])
    settle(kernel)
    choose(kernel, cover_run["pipeline_run_id"])
    return title_run["pipeline_run_id"], cover_run["pipeline_run_id"]


def test_approved_chain_creates_one_book_and_canonical_story_state(creative):
    kernel, _, analysis_run = creative
    _, cover_run = selected_cover(kernel, analysis_run)
    kernel.books = BookService(kernel)
    client = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    headers = {"x-api-key": "test"}
    assert client.get("/api/books", headers={}).status_code == 401
    context = client.get(f"/api/books/bootstrap-context/{cover_run}", headers=headers).json()
    first = client.post("/api/books", json=context, headers=headers)
    assert first.status_code == 201, first.text
    payload = first.json()
    assert payload["book"]["book_id"] == context["book_id"]
    assert payload["book"]["status"] == "ready"
    assert payload["state"]["version"] == 1
    assert len(payload["state"]["content_hash"]) == 64
    assert payload["state"]["source_refs"] == [context[k] for k in
        ("opportunity_artifact_id", "title_artifact_id", "cover_artifact_id")]
    assert set(payload["state"]["content"]) == set(StoryStateContent.model_fields)
    assert payload["state"]["content"]["StoryBible"]["title"] == payload["book"]["book_title"]
    assert client.post("/api/books", json=context, headers=headers).json() == payload
    assert len(kernel.storage.list("books")) == len(kernel.storage.list("story_states")) == 1
    assert len(kernel.storage.list("artifacts", artifact_type="StoryState")) == 1
    assert client.get(f"/api/books/{context['book_id']}", headers=headers).json() == payload
    assert client.get(f"/api/books/{context['book_id']}/story-state", headers=headers).json() == payload["state"]
    assert len(client.get("/api/books", headers=headers).json()) == 1
    assert kernel.storage.list("agent_states") == []
    client.close()


def test_legacy_book_record_remains_readable_without_becoming_canonical(creative):
    kernel, _, _ = creative
    kernel.books = BookService(kernel)
    kernel.storage.ensure("books", {"book_id": "BK-legacy", "book_title": "Earlier draft",
        "status": "planning", "created_at": "2026-01-01T00:00:00Z", "mini_bible": "Legacy content"})
    view = kernel.books.read("BK-legacy")
    assert view["book"]["mini_bible"] == "Legacy content"
    assert view["legacy"] is True
    assert view["state"] is None
    assert kernel.books.list_books()[0]["book_id"] == "BK-legacy"


def test_unapproved_or_stale_source_never_commits_book(creative):
    kernel, _, analysis_run = creative
    title_run = enqueue(kernel, "titles", analysis_run)
    settle(kernel)
    choose(kernel, title_run["pipeline_run_id"])
    cover_run = enqueue(kernel, "covers", title_run["pipeline_run_id"])
    settle(kernel)
    kernel.books = BookService(kernel)
    with pytest.raises(TransitionConflict):
        kernel.books.context(cover_run["pipeline_run_id"])
    choose(kernel, cover_run["pipeline_run_id"])
    context = kernel.books.context(cover_run["pipeline_run_id"])
    with pytest.raises(TransitionConflict):
        kernel.books.bootstrap({**context, "cover_artifact_id": "AR-other"})
    enqueue(kernel, "titles", analysis_run)  # reserves a newer version, making the chain stale
    with pytest.raises(TransitionConflict):
        kernel.books.bootstrap(context)
    assert kernel.storage.list("books") == []
    assert kernel.storage.list("story_states") == []


def test_interrupted_final_pointer_update_recovers_exactly_once(creative, monkeypatch):
    kernel, _, analysis_run = creative
    _, cover_run = selected_cover(kernel, analysis_run)
    kernel.books = BookService(kernel)
    context = kernel.books.context(cover_run)
    original = kernel.storage.update
    failed = False

    def interrupt(collection, domain_id, fields):
        nonlocal failed
        if collection == "books" and not failed:
            failed = True
            raise RuntimeError("process stopped before ready pointer")
        return original(collection, domain_id, fields)

    monkeypatch.setattr(kernel.storage, "update", interrupt)
    with pytest.raises(RuntimeError, match="process stopped"):
        kernel.books.bootstrap(context)
    monkeypatch.setattr(kernel.storage, "update", original)
    assert kernel.storage.list("books")[0]["status"] == "initializing"
    result = kernel.books.bootstrap(context)
    assert result["book"]["status"] == "ready"
    assert len(kernel.storage.list("books")) == 1
    assert len(kernel.storage.list("story_states")) == 1
    assert len(kernel.storage.list("artifacts", artifact_type="StoryState")) == 1


def test_corrupted_ready_state_is_not_exposed_as_canonical(creative):
    kernel, _, analysis_run = creative
    _, cover_run = selected_cover(kernel, analysis_run)
    kernel.books = BookService(kernel)
    context = kernel.books.context(cover_run)
    result = kernel.books.bootstrap(context)
    state_id = result["state"]["story_state_id"]
    kernel.storage.update("story_states", state_id, {"source_refs_json": "[\"AR-wrong\"]"})
    with pytest.raises(AmbiguousWrite, match="provenance"):
        kernel.books.context_provider.get(context["book_id"])
