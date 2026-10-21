"""ZEN-39: persisted planning identity, approval and recovery boundaries."""

import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.harness import encode, stable_id, TransitionConflict
from app.main import create_app
from app.harness import PermanentStepFailure
from app.storage import AmbiguousWrite
from app.story_planning import StoryPlanningService
from tests.test_book_context_integrity import assert_only_reads, raw_row
from tests.test_story_planning import approve_bible, bible, brief, settle

pytest_plugins = ("tests.test_creative_workflow", "tests.test_story_planning")

HEADERS = {"x-api-key": "test"}


@pytest.fixture
def boundary(planning):
    kernel, provider, book_id, _ = planning
    transport = kernel.storage._repos["artifacts"]._client._http._transport.handler
    # Control the actual kernel with tick(), as the planning fixture does. An
    # autonomous lifespan scheduler would race the frozen external snapshots.
    api = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    try:
        yield kernel, provider, book_id, transport, api
    finally:
        api.close()


def enqueue(boundary, kind):
    kernel, provider, book_id, _, api = boundary
    if kind == "bible":
        context = f"/api/books/{book_id}/bible/context"
        path = f"/api/books/{book_id}/bibles"
    else:
        approve_bible(kernel, provider, book_id)
        context = f"/api/books/{book_id}/chapters/1/brief/context"
        path = f"/api/books/{book_id}/chapters/1/briefs"
    response = api.get(context, headers=HEADERS)
    assert response.status_code == 200
    request = response.json()
    response = api.post(path, headers=HEADERS, json=request)
    assert response.status_code == 201
    return path, request, kernel.get(response.json()["pipeline_run_id"])


def frozen(boundary):
    _, provider, _, transport, _ = boundary
    transport.calls.clear()
    return copy.deepcopy(transport.tables), list(provider.calls)


def unchanged(boundary, before):
    _, provider, _, transport, _ = boundary
    assert transport.tables == before[0]
    assert provider.calls == before[1]
    assert_only_reads(transport)


@pytest.mark.parametrize("kind", ["bible", "brief"])
@pytest.mark.parametrize("stage", ["queued", "settled"])
def test_exact_request_replay_is_read_only_and_conflicting_request_refused(boundary, kind, stage):
    kernel, provider, _, _, api = boundary
    path, request, run = enqueue(boundary, kind)
    if stage == "settled":
        provider.outputs.append(bible() if kind == "bible" else brief())
        settle(kernel, 2)
    current = kernel.get(run["pipeline_run_id"])
    before = frozen(boundary)
    repeated = api.post(path, headers=HEADERS, json=request)
    assert repeated.status_code == 201
    assert repeated.json() == {key: value for key, value in current.items() if key != "steps"}
    assert kernel.get(run["pipeline_run_id"]) == current
    conflict = api.post(path, headers=HEADERS, json={**request, "feedback": "different request"})
    assert conflict.status_code == 409
    assert "already reserved with different inputs" in conflict.json()["detail"]
    unchanged(boundary, before)


@pytest.mark.parametrize("kind", ["bible", "brief"])
@pytest.mark.parametrize("stage", ["queued", "awaiting_review"])
def test_next_version_cannot_bypass_an_active_planning_run(boundary, kind, stage):
    kernel, provider, _, _, api = boundary
    path, request, _ = enqueue(boundary, kind)
    if stage == "awaiting_review":
        provider.outputs.append(bible() if kind == "bible" else brief())
        # Bible waits at its human gate; a brief is still pending materialization.
        settle(kernel, 2 if kind == "bible" else 1)
    before = frozen(boundary)
    response = api.post(path, headers=HEADERS, json={**request, "version": 2})
    assert response.status_code == 409
    assert "Resolve the current" in response.json()["detail"]
    unchanged(boundary, before)


@pytest.mark.parametrize("field,value", [("state_artifact_id", "AR-stale"),
                                        ("state_version", 1), ("version", 3)])
def test_new_brief_refuses_stale_state_or_skipped_version_before_reservation(boundary, field, value):
    kernel, provider, book_id, _, api = boundary
    approve_bible(kernel, provider, book_id)
    request = kernel.story_planning.brief_context(book_id, 1)
    before = frozen(boundary)
    response = api.post(f"/api/books/{book_id}/chapters/1/briefs", headers=HEADERS,
                        json={**request, field: value})
    assert response.status_code == 409
    assert "source or version changed" in response.json()["detail"]
    unchanged(boundary, before)


def test_no_bible_cannot_produce_brief_context_or_reserve_a_brief(boundary):
    kernel, _, book_id, _, api = boundary
    state = kernel.books.read(book_id)["state"]
    before = frozen(boundary)
    response = api.get(f"/api/books/{book_id}/chapters/1/brief/context", headers=HEADERS)
    assert response.status_code == 409 and "Approve the initial StoryBible" in response.json()["detail"]
    response = api.post(f"/api/books/{book_id}/chapters/1/briefs", headers=HEADERS, json={
        "book_id": book_id, "chapter_no": 1, "state_artifact_id": state["artifact_id"],
        "state_version": state["version"], "version": 1, "feedback": ""})
    assert response.status_code == 409 and "Approve the initial StoryBible" in response.json()["detail"]
    unchanged(boundary, before)


@pytest.mark.parametrize("kind", ["bible", "brief"])
@pytest.mark.parametrize("fault", ["bad_json", "no_steps", "no_request", "definition_book", "run_identity"])
def test_damaged_external_definition_refused_without_repair_and_restores_exactly(boundary, kind, fault):
    _, _, _, transport, api = boundary
    path, _, run = enqueue(boundary, kind)
    original = copy.deepcopy(transport.tables)
    row = raw_row(transport, "pipeline_runs", "pipeline_run_id", run["pipeline_run_id"])
    definition = json.loads(row["fields"]["definition_json"])
    if fault == "bad_json":
        row["fields"]["definition_json"] = "{"
    elif fault == "no_steps":
        definition["steps"] = []
    elif fault == "no_request":
        definition["steps"][0]["input"].pop("request")
    elif fault == "definition_book":
        definition["book_id"] = "BK-another-book"
    else:
        row["fields"]["pipeline_run_id"] = "PR-forged-identity"
    if fault != "bad_json":
        row["fields"]["definition_json"] = encode(definition)
    before = frozen(boundary)
    response = api.get(path, headers=HEADERS)
    assert response.status_code == 503
    assert response.json() == {"detail": "AmbiguousWrite", "reconciliation_required": True}
    unchanged(boundary, before)
    transport.tables = original
    before = frozen(boundary)
    response = api.get(path, headers=HEADERS)
    assert response.status_code == 200
    assert len(response.json()) == 1 and response.json()[0]["run"] == run
    unchanged(boundary, before)


@pytest.mark.parametrize("fault", ["wrong_step", "rejection_selects_artifact", "gate_output_changed"])
def test_bible_decision_refuses_wrong_gate_or_artifact_without_durable_approval(boundary, fault):
    kernel, provider, book_id, transport, api = boundary
    _, _, run = enqueue(boundary, "bible")
    provider.outputs.append(bible())
    settle(kernel, 2)
    view = kernel.story_planning.read(run["pipeline_run_id"])
    gate = next(s for s in view["run"]["steps"] if s["step_key"] == "review")
    request = {"step_id": gate["step_run_id"], "artifact_id": view["artifact"]["artifact_id"],
               "expected_version": gate["output_version"], "action": "approve", "operator": "editor"}
    original = copy.deepcopy(transport.tables)
    if fault == "wrong_step":
        request["step_id"] = run["steps"][0]["step_run_id"]
    elif fault == "rejection_selects_artifact":
        request["action"] = "reject"
    else:
        row = raw_row(transport, "step_runs", "step_run_id", gate["step_run_id"])
        output = json.loads(row["fields"]["output_json"])
        output["artifact_id"] = "AR-foreign-bible"
        row["fields"]["output_json"] = encode(output)
    before = frozen(boundary)
    response = api.post(f"/api/story-planning/runs/{run['pipeline_run_id']}/decision",
                        headers=HEADERS, json=request)
    assert response.status_code == 409
    expected = {"gate_output_changed": "exact Bible artifact", "wrong_step": "Bible review step",
                "rejection_selects_artifact": "Only approval selects"}
    assert expected[fault] in response.json()["detail"]
    unchanged(boundary, before)

    transport.tables = original
    request.update(step_id=gate["step_run_id"], action="approve")
    assert api.post(f"/api/story-planning/runs/{run['pipeline_run_id']}/decision",
                    headers=HEADERS, json=request).status_code == 200
    calls = list(provider.calls)
    settle(kernel, 1)
    state = kernel.books.read(book_id)["state"]
    assert state["version"] == 2 and state["source_refs"][1] == view["artifact"]["artifact_id"]
    assert provider.calls == calls


@pytest.mark.parametrize("missing", ["books", "semantic", "story_architect", "chapter_planner"])
def test_planning_configuration_fails_before_handler_registration(boundary, monkeypatch, missing):
    kernel, provider, _, transport, _ = boundary
    handlers = dict(kernel.handlers)
    guards = dict(kernel.approval_guards)
    if missing in {"books", "semantic"}:
        monkeypatch.setattr(kernel, missing, None)
    else:
        monkeypatch.delitem(kernel.model_router.routes, missing)
    before = frozen(boundary)
    with pytest.raises(ValueError, match="Story planning requires"):
        StoryPlanningService(kernel)
    assert kernel.handlers == handlers and kernel.approval_guards == guards
    assert transport.tables == before[0] and provider.calls == before[1]
    assert not transport.calls


@pytest.mark.parametrize("fault", ["wrong_workflow", "rejection_selects_artifact"])
def test_registered_approval_guard_independently_refuses_invalid_contract(boundary, fault):
    """Registered guard contract, not a claim these inputs passed the public API."""
    kernel, provider, _, _, _ = boundary
    _, _, run = enqueue(boundary, "brief" if fault == "wrong_workflow" else "bible")
    if fault == "wrong_workflow":
        step, choice = run["steps"][0], ""
    else:
        provider.outputs.append(bible())
        settle(kernel, 2)
        view = kernel.story_planning.read(run["pipeline_run_id"])
        step = next(s for s in view["run"]["steps"] if s["step_key"] == "review")
        choice = view["artifact"]["artifact_id"]
    before = frozen(boundary)
    with pytest.raises(TransitionConflict, match=("Wrong approval workflow" if fault == "wrong_workflow"
                                                else "Only approval selects the Bible artifact")):
        kernel.approval_guards["story_bible.review"](step, "reject", choice)
    unchanged(boundary, before)


def pending_commit(boundary):
    kernel, provider, _, _, _ = boundary
    _, _, run = enqueue(boundary, "bible")
    provider.outputs.append(bible())
    settle(kernel, 2)
    view = kernel.story_planning.read(run["pipeline_run_id"])
    gate = next(s for s in view["run"]["steps"] if s["step_key"] == "review")
    kernel.story_planning.decide_bible(run["pipeline_run_id"], step_id=gate["step_run_id"],
        artifact_id=view["artifact"]["artifact_id"], expected_version=gate["output_version"],
        action="approve", operator="editor")
    step = next(s for s in kernel.get(run["pipeline_run_id"])["steps"] if s["step_key"] == "commit")
    assert step["status"] == "pending"
    return view, step


def test_registered_commit_replay_preserves_exact_canonical_version_and_rejects_changed_provenance(boundary):
    """Actual registered handler/repository boundary, with durable prior approval."""
    kernel, provider, book_id, transport, _ = boundary
    view = approve_bible(kernel, provider, book_id)
    step = next(s for s in view["run"]["steps"] if s["step_key"] == "commit")
    state = kernel.books.read(book_id)["state"]
    handler = kernel.handlers["story_bible.commit"]
    before = frozen(boundary)
    assert handler(step) == {"output_refs": [state["artifact_id"]]}
    unchanged(boundary, before)
    original = copy.deepcopy(transport.tables)
    refs = ["AR-other-base", "AR-other-bible"]
    book = raw_row(transport, "books", "book_id", book_id)
    projection = raw_row(transport, "story_states", "story_state_id", state["story_state_id"])
    artifact = raw_row(transport, "artifacts", "artifact_id", state["artifact_id"])
    payload = json.loads(artifact["fields"]["payload_json"])
    payload["source_refs"] = refs
    artifact["fields"]["payload_json"] = encode(payload)
    book["fields"]["source_refs_json"] = projection["fields"]["source_refs_json"] = encode(refs)
    # The three external records agree; the commit must still require its own
    # exact base/Bible lineage rather than merely accepting any canonical refs.
    before = frozen(boundary)
    with pytest.raises(AmbiguousWrite, match="unexpected provenance"):
        handler(step)
    unchanged(boundary, before)
    transport.tables = original
    before = frozen(boundary)
    assert handler(step) == {"output_refs": [state["artifact_id"]]}
    assert kernel.books.read(book_id)["state"] == state
    unchanged(boundary, before)


@pytest.mark.parametrize("fault", ["model_config", "newer_external_run"])
def test_registered_commit_checks_fresh_configuration_and_latest_run_before_writes(boundary, fault, monkeypatch):
    kernel, provider, book_id, transport, _ = boundary
    view, step = pending_commit(boundary)
    original = copy.deepcopy(transport.tables)
    route = kernel.model_router.routes["story_architect"]
    if fault == "model_config":
        monkeypatch.setitem(kernel.model_router.routes, "story_architect",
                            route.model_copy(update={"max_retries": route.max_retries + 1}))
    else:
        row = copy.deepcopy(raw_row(transport, "pipeline_runs", "pipeline_run_id", view["run"]["pipeline_run_id"]))
        definition = json.loads(row["fields"]["definition_json"])
        definition["steps"][0]["input"]["request"]["version"] = 2
        row["record_id"] = "rec-external-newer-bible"
        row["fields"].update(pipeline_run_id=stable_id("PR-", kernel.story_planning.identity("bible", book_id, 2)),
                              definition_json=encode(definition))
        transport.tables["pipeline_runs"][row["record_id"]] = row
    before = frozen(boundary)
    with pytest.raises(AmbiguousWrite if fault == "model_config" else PermanentStepFailure):
        kernel.handlers["story_bible.commit"](step)
    unchanged(boundary, before)
    transport.tables = original
    monkeypatch.setitem(kernel.model_router.routes, "story_architect", route)
    calls = list(provider.calls)
    settle(kernel, 1)
    state = kernel.books.read(book_id)["state"]
    assert state["version"] == 2 and state["source_refs"][1] == view["artifact"]["artifact_id"]
    assert provider.calls == calls


def test_conflicting_state_projection_retains_proposal_and_recovers_same_approved_commit(boundary):
    kernel, provider, book_id, transport, _ = boundary
    view, step = pending_commit(boundary)
    base = kernel.books.read(book_id)["state"]
    state_id = stable_id("SS-", book_id + "/2")
    bad = {"record_id": "rec-external-state-conflict", "fields": {"story_state_id": state_id,
           "book_id": "BK-foreign", "version": 2, "artifact_id": "AR-foreign"}}
    transport.tables["story_states"][bad["record_id"]] = copy.deepcopy(bad)
    book_before = copy.deepcopy(transport.tables["books"])
    calls = list(provider.calls)
    with pytest.raises(AmbiguousWrite, match="projection conflicts"):
        kernel.handlers["story_bible.commit"](step)
    assert transport.tables["books"] == book_before
    assert transport.tables["story_states"][bad["record_id"]] == bad
    assert kernel.books.read(book_id)["state"] == base and provider.calls == calls
    proposed = kernel.artifacts.get(stable_id("AR-", f"books/{book_id}/story-state/2"))
    assert proposed["source_refs"] == [base["artifact_id"], view["artifact"]["artifact_id"]]
    # Correct only the deliberately damaged external projection. Preserve the
    # actual immutable proposal produced before the failed pointer update.
    transport.tables["story_states"][bad["record_id"]]["fields"] = {
        "story_state_id": state_id, "book_id": book_id, "version": 2,
        "artifact_id": proposed["artifact_id"], "content_hash": proposed["content_hash"],
        "source_refs_json": encode(proposed["source_refs"]), "created_at": proposed["created_at"]}
    settle(kernel, 1)
    state = kernel.books.read(book_id)["state"]
    assert state["version"] == 2 and state["artifact_id"] == proposed["artifact_id"]
    assert len(kernel.storage.list("story_states", book_id=book_id)) == 2
    assert len(kernel.storage.list("artifacts", artifact_type="StoryState")) == 2
    assert provider.calls == calls


def test_brief_workflow_cannot_be_approved_as_a_bible(boundary):
    _, _, _, _, api = boundary
    _, _, run = enqueue(boundary, "brief")
    before = frozen(boundary)
    response = api.post(f"/api/story-planning/runs/{run['pipeline_run_id']}/decision", headers=HEADERS,
                        json={"step_id": run["steps"][0]["step_run_id"], "artifact_id": "",
                              "expected_version": 1, "action": "reject", "operator": "editor"})
    assert response.status_code == 409 and "Bible review step" in response.json()["detail"]
    unchanged(boundary, before)


@pytest.mark.parametrize("kind", ["bible", "brief"])
def test_planning_inventory_does_not_mix_other_books_into_history(boundary, kind):
    _, _, _, transport, api = boundary
    path, _, run = enqueue(boundary, kind)
    original = copy.deepcopy(transport.tables)
    row = copy.deepcopy(raw_row(transport, "pipeline_runs", "pipeline_run_id", run["pipeline_run_id"]))
    definition = json.loads(row["fields"]["definition_json"])
    definition["book_id"] = "BK-other-book"
    definition["steps"][0]["input"]["request"]["book_id"] = "BK-other-book"
    row["record_id"] = "rec-other-book-planning"
    row["fields"].update(book_id="BK-other-book", pipeline_run_id="PR-other-book-planning",
                          definition_json=encode(definition))
    transport.tables["pipeline_runs"][row["record_id"]] = row
    before = frozen(boundary)
    response = api.get(path, headers=HEADERS)
    assert response.status_code == 200
    assert len(response.json()) == 1 and response.json()[0]["run"] == run
    unchanged(boundary, before)
    transport.tables = original
    before = frozen(boundary)
    response = api.get(path, headers=HEADERS)
    assert response.status_code == 200 and response.json()[0]["run"] == run
    unchanged(boundary, before)


def test_approved_bible_with_no_brief_cannot_unblock_chapter_generation(boundary):
    kernel, provider, book_id, _, api = boundary
    approve_bible(kernel, provider, book_id)
    before = frozen(boundary)
    response = api.get(f"/api/books/{book_id}/chapters/1/brief/eligible", headers=HEADERS)
    assert response.status_code == 409
    assert response.json() == {"detail": "No current policy-eligible ChapterBrief"}
    unchanged(boundary, before)


def test_registered_bible_commit_cannot_consume_a_brief_run(boundary):
    """Handler contract: invalid persisted workflow selection fails before writes."""
    kernel, _, _, _, _ = boundary
    _, _, run = enqueue(boundary, "brief")
    before = frozen(boundary)
    with pytest.raises(AmbiguousWrite, match="Bible commit manifest changed"):
        kernel.handlers["story_bible.commit"](run["steps"][0])
    unchanged(boundary, before)
