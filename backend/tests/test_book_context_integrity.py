"""Canonical book reads reject damaged external evidence without repairing it."""

import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.books import BookService
from app.config import Settings
from app.feishu.table_map import FIELD_MAPS
from app.generation import digest
from app.harness import encode, stable_id
from app.main import create_app
from tests.test_book_bootstrap import selected_cover

pytest_plugins = ("tests.test_creative_workflow",)


@pytest.fixture
def sources(creative):
    kernel, provider, analysis_run = creative
    _, cover_run = selected_cover(kernel, analysis_run)
    kernel.books = BookService(kernel)
    request = kernel.books.context(cover_run)
    transport = kernel.storage._repos["artifacts"]._client._http._transport.handler
    # Real Base tables already exist. Prime the lazy HTTP fixture's empty
    # containers before freezing the no-business-mutation baseline.
    assert kernel.storage.list("books") == []
    assert kernel.storage.list("story_states") == []
    return kernel, provider, request, transport


def raw_row(transport, collection, key, value):
    field = FIELD_MAPS[collection][key]
    return next(
        row
        for row in transport.tables[collection].values()
        if row["fields"].get(field) == value
    )


def assert_only_reads(transport):
    assert transport.calls
    assert all(
        request.method == "GET"
        or request.method == "POST"
        and request.url.path.endswith("/records/search")
        for request in transport.calls
    )


@pytest.mark.parametrize(
    "fault",
    [
        "missing_book",
        "not_ready",
        "missing_state_pointer",
        "missing_state",
        "foreign_state_book",
        "different_state_version",
        "missing_artifact",
        "bad_artifact_json",
        "bad_state_refs_json",
        "bad_book_refs_json",
        "wrong_artifact_type",
        "wrong_artifact_version",
        "wrong_artifact_logical",
        "wrong_state_hash",
        "wrong_book_hash",
        "wrong_state_refs",
        "wrong_book_refs",
        "invalid_story_schema",
        "boolean_book_version",
        "boolean_state_version",
    ],
)
def test_canonical_api_refuses_external_damage_then_reads_restored_evidence(
    sources, fault
):
    kernel, provider, request, transport = sources
    view = kernel.books.bootstrap(request)
    book_id = request["book_id"]
    baseline = copy.deepcopy(transport.tables)
    book = raw_row(transport, "books", "book_id", book_id)
    state = raw_row(
        transport, "story_states", "story_state_id", view["state"]["story_state_id"]
    )
    artifact = raw_row(
        transport, "artifacts", "artifact_id", view["state"]["artifact_id"]
    )
    b, s, a = book["fields"], state["fields"], artifact["fields"]
    payload = json.loads(a["payload_json"])
    if fault == "missing_book":
        del transport.tables["books"][book["record_id"]]
    elif fault == "not_ready":
        b["status"] = "initializing"
    elif fault == "missing_state_pointer":
        b.pop("story_state_id")
    elif fault == "missing_state":
        del transport.tables["story_states"][state["record_id"]]
    elif fault == "foreign_state_book":
        s["book_id"] = "BK-another-book"
    elif fault == "different_state_version":
        s["version"] = 2
    elif fault == "missing_artifact":
        del transport.tables["artifacts"][artifact["record_id"]]
    elif fault == "bad_artifact_json":
        a["payload_json"] = "{"
    elif fault == "bad_state_refs_json":
        s["source_refs_json"] = "["
    elif fault == "bad_book_refs_json":
        b["source_refs_json"] = "["
    elif fault == "wrong_artifact_type":
        payload["artifact_type"] = "ChapterBrief"
        a["artifact_type"] = "ChapterBrief"
        a["payload_json"] = encode(payload)
    elif fault in {"wrong_artifact_version", "wrong_artifact_logical"}:
        replacement = copy.deepcopy(artifact)
        replacement["record_id"] = "rec-corrupt-boundary"
        payload["version"] = 2 if fault == "wrong_artifact_version" else 1
        if fault == "wrong_artifact_logical":
            payload["logical_id"] = "books/BK-another-book/story-state"
        payload["artifact_id"] = stable_id(
            "AR-", payload["logical_id"] + "/" + str(payload["version"])
        )
        replacement["fields"].update(
            artifact_id=payload["artifact_id"],
            logical_id=payload["logical_id"],
            version=payload["version"],
            payload_json=encode(payload),
        )
        transport.tables["artifacts"][replacement["record_id"]] = replacement
        s["artifact_id"] = payload["artifact_id"]
    elif fault == "wrong_state_hash":
        s["content_hash"] = "0" * 64
    elif fault == "wrong_book_hash":
        b["story_state_hash"] = "0" * 64
    elif fault == "wrong_state_refs":
        s["source_refs_json"] = encode(["AR-another-source"])
    elif fault == "wrong_book_refs":
        b["source_refs_json"] = encode(["AR-another-source"])
    elif fault == "invalid_story_schema":
        payload["content"].pop("World")
        payload["content_hash"] = digest(payload["content"])
        a["payload_json"] = encode(payload)
        s["content_hash"] = b["story_state_hash"] = payload["content_hash"]
    elif fault == "boolean_book_version":
        b["story_state_version"] = True
    else:
        s["version"] = True
    damaged = copy.deepcopy(transport.tables)
    calls = list(provider.calls)
    transport.calls.clear()
    api = TestClient(
        create_app(Settings(_env_file=None, BACKEND_API_KEY="test"), kernel=kernel)
    )
    response = api.get(
        f"/api/books/{book_id}/story-state", headers={"x-api-key": "test"}
    )
    missing = fault in {"missing_book", "not_ready"}
    assert response.status_code == (404 if missing else 503)
    if not missing:
        assert response.json()["reconciliation_required"] is True
        assert "content" not in response.json()
        if fault.startswith("boolean_"):
            assert response.json()["detail"] == "FeishuAPIError"
    assert transport.tables == damaged
    assert_only_reads(transport)
    assert provider.calls == calls
    transport.tables = baseline
    restored = api.get(
        f"/api/books/{book_id}/story-state", headers={"x-api-key": "test"}
    )
    assert restored.status_code == 200 and restored.json() == view["state"]
    assert transport.tables == baseline and provider.calls == calls
    assert_only_reads(transport)
    api.close()


@pytest.mark.parametrize(
    "field", ["title_artifact_id", "opportunity_artifact_id", "cover_artifact_id"]
)
def test_unmatched_approved_request_never_reserves_a_book(sources, field):
    kernel, provider, request, transport = sources
    wrong = {**request, field: "AR-another-selection"}
    if field == "cover_artifact_id":
        wrong["book_id"] = stable_id("BK-", wrong[field])
    baseline = copy.deepcopy(transport.tables)
    calls = list(provider.calls)
    transport.calls.clear()
    api = TestClient(
        create_app(Settings(_env_file=None, BACKEND_API_KEY="test"), kernel=kernel)
    )
    response = api.post("/api/books", json=wrong, headers={"x-api-key": "test"})
    assert response.status_code == 409
    assert transport.tables == baseline and provider.calls == calls
    assert_only_reads(transport)
    assert kernel.storage.list("books") == []
    assert kernel.storage.list("story_states") == []
    created = api.post("/api/books", json=request, headers={"x-api-key": "test"})
    assert created.status_code == 201 and created.json()["book"]["status"] == "ready"
    assert provider.calls == calls
    api.close()


@pytest.mark.parametrize(
    "fault",
    ["bootstrap_hash", "initial_state_pointer", "book_projection", "state_projection"],
)
def test_conflicting_partial_bootstrap_preserves_evidence_and_recovers_exactly(
    sources, fault
):
    kernel, provider, request, transport = sources
    original = kernel.books.bootstrap(request)
    baseline = copy.deepcopy(transport.tables)
    book = raw_row(transport, "books", "book_id", request["book_id"])["fields"]
    state = raw_row(
        transport, "story_states", "story_state_id", original["state"]["story_state_id"]
    )["fields"]
    if fault == "bootstrap_hash":
        book["bootstrap_hash"] = "0" * 64
    else:
        book["status"] = "initializing"
        if fault == "initial_state_pointer":
            book["story_state_id"] = "SS-another-state"
        elif fault == "book_projection":
            book[FIELD_MAPS["books"]["genre"]] = "Unrelated genre"
        else:
            state["content_hash"] = "0" * 64
    damaged = copy.deepcopy(transport.tables)
    calls = list(provider.calls)
    transport.calls.clear()
    api = TestClient(
        create_app(Settings(_env_file=None, BACKEND_API_KEY="test"), kernel=kernel)
    )
    response = api.post("/api/books", json=request, headers={"x-api-key": "test"})
    assert response.status_code == (
        409 if fault in {"bootstrap_hash", "initial_state_pointer"} else 503
    )
    assert transport.tables == damaged and provider.calls == calls
    assert_only_reads(transport)
    transport.tables = baseline
    replay = api.post("/api/books", json=request, headers={"x-api-key": "test"})
    assert replay.status_code == 201 and replay.json() == original
    assert transport.tables == baseline and provider.calls == calls
    assert_only_reads(transport)
    api.close()


def test_missing_book_and_initializing_book_have_distinct_read_states(sources):
    kernel, _, request, _ = sources
    api = TestClient(
        create_app(Settings(_env_file=None, BACKEND_API_KEY="test"), kernel=kernel)
    )
    headers = {"x-api-key": "test"}
    assert api.get("/api/books/BK-missing", headers=headers).status_code == 404
    original = kernel.books.bootstrap(request)
    kernel.storage.update("books", request["book_id"], {"status": "initializing"})
    response = api.get(f"/api/books/{request['book_id']}", headers=headers)
    assert response.status_code == 200
    assert response.json() == {
        "book": {**original["book"], "status": "initializing"},
        "state": None,
        "legacy": False,
    }
    api.close()


def test_book_service_requires_artifact_runtime_even_with_creative_service(sources):
    kernel, _, _, _ = sources
    del kernel.artifacts
    with pytest.raises(ValueError, match="requires creative selections and artifacts"):
        BookService(kernel)


def test_ready_book_replay_survives_one_stale_absence_without_duplicate_write(sources):
    import httpx

    kernel, provider, request, transport = sources
    expected = kernel.books.bootstrap(request)
    baseline = copy.deepcopy(transport.tables)
    calls = list(provider.calls)
    wire = kernel.storage._repos["books"]._client._http._transport
    injected = []

    def stale_once(req):
        response = transport(req)
        if not injected and req.url.path.endswith("/tables/books/records/search"):
            injected.append(True)
            return httpx.Response(
                200, json={"code": 0, "data": {"items": [], "has_more": False}}
            )
        return response

    wire.handler = stale_once
    transport.calls.clear()
    try:
        assert kernel.books.bootstrap(request) == expected
        assert injected == [True]
        assert transport.tables == baseline and provider.calls == calls
        assert_only_reads(transport)
    finally:
        wire.handler = transport


def test_title_choice_changed_between_source_reads_stops_bootstrap_context(sources):
    kernel, provider, request, transport = sources
    cover_state, _ = kernel.creative.selected_state("covers", request["cover_run_id"])
    title_run = cover_state["request"]["source_run_id"]
    title_state, selected = kernel.creative.selected_state("titles", title_run)
    other = next(
        item
        for item in title_state["candidates"]
        if item["artifact_id"] != selected["artifact_id"]
    )
    decision = title_state["decision"]
    approval = raw_row(
        transport, "approval_events", "approval_id", decision["approval_id"]
    )
    baseline = copy.deepcopy(transport.tables)
    calls = list(provider.calls)
    wire = kernel.storage._repos["books"]._client._http._transport
    injected = []

    def change_after_reply(req):
        response = transport(req)
        if req.url.path.endswith("/tables/approval_events/records/search"):
            criteria = json.loads(req.content)["filter"]["conditions"]
            if not injected and any(
                condition["value"] == [decision["approval_id"]]
                for condition in criteria
            ):
                injected.append(True)
                approval["fields"]["choice_id"] = other["artifact_id"]
        return response

    wire.handler = change_after_reply
    transport.calls.clear()
    try:
        from app.harness import TransitionConflict

        with pytest.raises(
            TransitionConflict, match="Cover no longer belongs to selected title"
        ):
            kernel.books.context(request["cover_run_id"])
        assert injected == [True]
        expected = copy.deepcopy(baseline)
        expected["approval_events"][approval["record_id"]]["fields"]["choice_id"] = (
            other["artifact_id"]
        )
        assert transport.tables == expected and provider.calls == calls
        assert_only_reads(transport)
        transport.tables = baseline
        assert kernel.books.context(request["cover_run_id"]) == request
        assert transport.tables == baseline and provider.calls == calls
    finally:
        wire.handler = transport


def test_book_rejects_inconsistent_upstream_title_view(sources, monkeypatch):
    """Isolated contract test: supply an invalid upstream selection view.

    Actual full-flow reads above separately verify real service/HTTP behavior;
    this deliberately faulty collaborator response is not a runtime-flow claim.
    """
    from app.harness import TransitionConflict

    kernel, provider, request, transport = sources
    original = kernel.creative.selected_state
    cover_state, _ = original("covers", request["cover_run_id"])
    title_run = cover_state["request"]["source_run_id"]
    state, artifact = original("titles", title_run)
    changed = copy.deepcopy(state)
    changed["request"]["source_artifact_id"] = "AR-inconsistent-upstream-source"

    def mismatched(kind, run_id):
        return (
            (changed, artifact)
            if (kind, run_id) == ("titles", title_run)
            else original(kind, run_id)
        )

    baseline = copy.deepcopy(transport.tables)
    calls = list(provider.calls)
    transport.calls.clear()
    with monkeypatch.context() as patch:
        patch.setattr(kernel.creative, "selected_state", mismatched)
        with pytest.raises(
            TransitionConflict, match="Title no longer belongs to approved opportunity"
        ):
            kernel.books.context(request["cover_run_id"])
    assert transport.tables == baseline and provider.calls == calls
    assert_only_reads(transport)
    assert kernel.books.context(request["cover_run_id"]) == request
