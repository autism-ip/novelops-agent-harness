"""Chapter planning freezes verified prior final prose, not per-Agent memory."""
import json

import pytest

from app.generation import CallContext, Prompt
from app.harness import encode, stable_id
from tests.test_story_planning import approve_bible, brief, settle

pytest_plugins = ("tests.test_creative_workflow", "tests.test_story_planning")


def seed_final(kernel, book_id, chapter_no=1, version_no=1, *, status="final"):
    """External canonical-history input fixture; full chapter execution is tested downstream."""
    snapshot = kernel.story_planning.snapshot(book_id)
    logical = f"books/{book_id}/chapters/{chapter_no}/versions"
    run_id = stable_id("PR-", f"history-fixture/{book_id}/{chapter_no}/{version_no}")
    draft_id, brief_id = f"AR-history-draft-{chapter_no}", f"AR-history-brief-{chapter_no}"
    verification = kernel.artifacts.save(logical_id=f"history-fixture/{book_id}/{chapter_no}/{version_no}/verification",
        version=1, artifact_type="ChapterVerification", content={"passed": True, "checks": {"chapter_number": True},
            "snapshot_artifact_id": snapshot["artifact_id"], "brief_artifact_id": brief_id,
            "draft_artifact_id": draft_id}, context=CallContext(run_id=run_id, step_id="history-verifier",
                chapter_id=f"{book_id}/{chapter_no}", input_refs=(snapshot["artifact_id"], brief_id, draft_id)),
        prompt=Prompt(version="history-fixture", template="Boundary fixture"), route="deterministic", provider="", model="")
    content = {"book_id": book_id, "chapter_no": chapter_no, "version_no": version_no,
        "title": f"The repaired garden gate {chapter_no}",
        "prose": "Mira returned the key and completed the promised repair before dawn. " * 8,
        "snapshot_artifact_id": snapshot["artifact_id"], "brief_artifact_id": brief_id,
        "verification_artifact_id": verification["artifact_id"]}
    refs = (snapshot["artifact_id"], brief_id, draft_id, verification["artifact_id"])
    artifact = kernel.artifacts.save(logical_id=logical, version=version_no, artifact_type="ChapterVersion",
        content=content, context=CallContext(run_id=run_id, step_id="history-verifier",
            chapter_id=f"{book_id}/{chapter_no}", input_refs=refs),
        prompt=Prompt(version="history-fixture", template="Boundary fixture"), route="deterministic", provider="", model="",
        creator="chapter-version-materializer")
    row = {"version_id": stable_id("CV-", logical + "/" + str(version_no)), "book_id": book_id,
        "chapter_no": chapter_no, "version_no": version_no, "chapter_title": content["title"],
        "content": content["prose"], "artifact_id": artifact["artifact_id"], "status": status,
        "content_hash": artifact["content_hash"], "source_refs_json": encode(refs),
        "story_context_snapshot_id": snapshot["artifact_id"], "verifier_artifact_id": verification["artifact_id"],
        "run_id": run_id, "created_at": artifact["created_at"]}
    kernel.storage.ensure("chapter_versions", row)
    return row, artifact


@pytest.fixture
def history(planning):
    kernel, provider, book_id, _ = planning
    approve_bible(kernel, provider, book_id)
    return kernel, provider, book_id


def test_planner_freezes_prior_final_content_and_exact_artifact_reference(history):
    kernel, provider, book_id = history
    row, artifact = seed_final(kernel, book_id)
    request = kernel.story_planning.brief_context(book_id, 2)
    run = kernel.story_planning.enqueue_brief(request)
    provider.outputs.append(brief())
    settle(kernel, 2)
    view = kernel.story_planning.read(run["pipeline_run_id"])
    snapshot = kernel.artifacts.get(view["snapshot_artifact_id"])
    previous = snapshot["content"]["prior_final_chapters"]
    assert len(previous) == 1
    assert previous[0] == {"version_id": row["version_id"], "artifact_id": artifact["artifact_id"],
        "chapter_no": 1, "version_no": 1, "content_hash": artifact["content_hash"], "content": artifact["content"]}
    assert snapshot["source_refs"][-1] == artifact["artifact_id"]
    inputs = json.loads(provider.messages[-1][1]["content"])
    assert inputs["snapshot"]["prior_final_chapters"] == previous
    assert view["eligible"] is True and view["artifact"]["source_refs"][0] == snapshot["artifact_id"]
    eligible, frozen = kernel.story_planning.eligible_brief(book_id, 2, _with_snapshot=True)
    assert eligible == view["artifact"] and frozen == snapshot
    assert "snapshot" not in view and "_with_snapshot" not in view
    assert kernel.storage.get("chapter_versions", row["version_id"]) == row
    assert kernel.artifacts.get(artifact["artifact_id"]) == artifact


def test_completed_brief_becomes_ineligible_when_prior_chapter_is_finalized(history):
    kernel, provider, book_id = history
    row, artifact = seed_final(kernel, book_id, status="review")
    request = kernel.story_planning.brief_context(book_id, 2)
    run = kernel.story_planning.enqueue_brief(request)
    provider.outputs.append(brief())
    settle(kernel, 2)
    first = kernel.story_planning.read(run["pipeline_run_id"])
    assert first["eligible"] is True
    kernel.storage.update("chapter_versions", row["version_id"], {"status": "final"})
    calls = list(provider.calls)
    assert kernel.story_planning.read(run["pipeline_run_id"])["eligible"] is False
    assert provider.calls == calls
    next_request = kernel.story_planning.brief_context(book_id, 2)
    next_run = kernel.story_planning.enqueue_brief(next_request)
    second = kernel.story_planning.read(next_run["pipeline_run_id"])
    assert second["snapshot_artifact_id"] != first["snapshot_artifact_id"]
    assert kernel.artifacts.get(second["snapshot_artifact_id"])["content"]["prior_final_chapters"][0]["artifact_id"] == artifact["artifact_id"]
    assert kernel.artifacts.get(first["artifact"]["artifact_id"]) == first["artifact"]


def assert_read_only(transport, offset):
    assert all(r.method == "GET" or r.method == "POST" and r.url.path.endswith("/records/search")
               for r in transport.calls[offset:])


def test_history_uses_nearest_previous_final_and_skips_future_and_nonfinal(history):
    kernel, _, book_id = history
    seed_final(kernel, book_id, 1)
    previous, artifact = seed_final(kernel, book_id, 3)
    seed_final(kernel, book_id, 4, status="review")
    seed_final(kernel, book_id, 5)
    request = kernel.story_planning.brief_context(book_id, 4)
    run = kernel.story_planning.enqueue_brief(request)
    view = kernel.story_planning.read(run["pipeline_run_id"])
    snapshot = kernel.artifacts.get(view["snapshot_artifact_id"])
    assert [item["version_id"] for item in snapshot["content"]["prior_final_chapters"]] == [previous["version_id"]]
    assert snapshot["source_refs"][-1] == artifact["artifact_id"]


def test_queued_plan_stops_before_model_when_prior_final_changes(history):
    from app.harness import TransitionConflict

    kernel, provider, book_id = history
    row, _ = seed_final(kernel, book_id, status="review")
    request = kernel.story_planning.brief_context(book_id, 2)
    run = kernel.story_planning.enqueue_brief(request)
    frozen = kernel.story_planning.read(run["pipeline_run_id"])
    snapshot = kernel.artifacts.get(frozen["snapshot_artifact_id"])
    kernel.storage.update("chapter_versions", row["version_id"], {"status": "final"})
    calls = list(provider.calls)
    settle(kernel, 1)
    failed = kernel.story_planning.read(run["pipeline_run_id"])
    assert failed["run"]["status"] == "failed" and failed["artifact"] is None
    assert provider.calls == calls
    assert kernel.artifacts.get(snapshot["artifact_id"]) == snapshot
    with pytest.raises(TransitionConflict, match="No current policy-eligible"):
        kernel.story_planning.eligible_brief(book_id, 2)
    transport = kernel.storage._repos["artifacts"]._client._http._transport.handler
    offset = len(transport.calls)
    assert kernel.story_planning.enqueue_brief(request)["pipeline_run_id"] == run["pipeline_run_id"]
    assert_read_only(transport, offset)
    assert provider.calls == calls


@pytest.mark.parametrize("fault", ["missing_artifact", "missing_verification", "row_hash", "row_refs",
    "row_run", "row_snapshot", "row_verifier", "row_prose", "row_title", "content_book",
    "content_chapter", "content_bool_version", "content_refs", "content_type", "verification_status",
    "verification_checks", "verification_type", "verification_refs", "verification_run"])
def test_ambiguous_final_history_blocks_planning_and_recovers_without_model(history, fault):
    from app.generation import digest
    from app.storage import AmbiguousWrite

    kernel, provider, book_id = history
    row, artifact = seed_final(kernel, book_id)
    original_row = kernel.storage.get("chapter_versions", row["version_id"])
    original_artifact = kernel.storage.get("artifacts", row["artifact_id"])
    original_verification = kernel.storage.get("artifacts", row["verifier_artifact_id"])
    if fault == "missing_artifact":
        kernel.storage.delete("artifacts", row["artifact_id"])
    elif fault == "missing_verification":
        kernel.storage.delete("artifacts", row["verifier_artifact_id"])
    elif fault.startswith("row_"):
        field = {"row_hash": "content_hash", "row_refs": "source_refs_json", "row_run": "run_id",
            "row_snapshot": "story_context_snapshot_id", "row_verifier": "verifier_artifact_id",
            "row_prose": "content", "row_title": "chapter_title"}[fault]
        kernel.storage.update("chapter_versions", row["version_id"], {field: "wrong-source"})
    else:
        original = original_verification if fault.startswith("verification_") else original_artifact
        payload = json.loads(original["payload_json"])
        if fault == "content_book":
            payload["content"]["book_id"] = "another-book"
        elif fault == "content_chapter":
            payload["content"]["chapter_no"] = 7
        elif fault == "content_bool_version":
            payload["content"]["version_no"] = True
        elif fault == "content_refs":
            payload["source_refs"] = payload["source_refs"][:2]
        elif fault == "content_type":
            payload["artifact_type"] = "UnapprovedDraft"
        elif fault == "verification_status":
            payload["content"]["passed"] = False
        elif fault == "verification_checks":
            payload["content"]["checks"]["chapter_number"] = False
        elif fault == "verification_type":
            payload["artifact_type"] = "CriticReport"
        elif fault == "verification_refs":
            payload["source_refs"] = []
        else:
            payload["run_id"] = "another-run"
        payload["content_hash"] = digest(payload["content"])
        kernel.storage.update("artifacts", original["artifact_id"], {"payload_json": encode(payload)})
        if not fault.startswith("verification_"):
            kernel.storage.update("chapter_versions", row["version_id"], {"content_hash": payload["content_hash"]})
    calls = list(provider.calls)
    transport = kernel.storage._repos["artifacts"]._client._http._transport.handler
    offset = len(transport.calls)
    request = kernel.story_planning.brief_context(book_id, 2)
    with pytest.raises(AmbiguousWrite, match="Prior final chapter provenance"):
        kernel.story_planning.enqueue_brief(request)
    assert_read_only(transport, offset)
    assert provider.calls == calls
    assert kernel.story_planning.list_briefs(book_id, 2) == []
    if fault == "missing_artifact":
        kernel.storage.ensure("artifacts", original_artifact)
    elif fault == "missing_verification":
        kernel.storage.ensure("artifacts", original_verification)
    else:
        kernel.storage.update("chapter_versions", row["version_id"], original_row)
        kernel.storage.update("artifacts", row["artifact_id"], {"payload_json": original_artifact["payload_json"]})
        kernel.storage.update("artifacts", row["verifier_artifact_id"], {"payload_json": original_verification["payload_json"]})
    run = kernel.story_planning.enqueue_brief(request)
    view = kernel.story_planning.read(run["pipeline_run_id"])
    assert kernel.artifacts.get(view["snapshot_artifact_id"])["content"]["prior_final_chapters"][0]["artifact_id"] == artifact["artifact_id"]
    assert provider.calls == calls
    assert kernel.storage.get("chapter_versions", row["version_id"]) == original_row


def test_duplicate_or_legacy_final_is_not_guessed_into_history(history):
    from app.storage import AmbiguousWrite

    kernel, provider, book_id = history
    row, _ = seed_final(kernel, book_id)
    kernel.storage.ensure("chapter_versions", {**row, "version_id": "CV-conflict", "version_no": 2})
    request = kernel.story_planning.brief_context(book_id, 2)
    calls = list(provider.calls)
    with pytest.raises(AmbiguousWrite, match="Multiple prior final"):
        kernel.story_planning.enqueue_brief(request)
    kernel.storage.delete("chapter_versions", "CV-conflict")
    kernel.storage.delete("chapter_versions", row["version_id"])
    kernel.storage.ensure("chapter_versions", {"version_id": "CV-legacy", "book_id": book_id,
        "chapter_no": 1, "version_no": 1, "status": "final", "content": "Legacy prose without immutable provenance"})
    with pytest.raises(AmbiguousWrite, match="Prior final chapter provenance"):
        kernel.story_planning.enqueue_brief(request)
    assert kernel.story_planning.list_briefs(book_id, 2) == [] and provider.calls == calls


@pytest.mark.parametrize("field,value", [("prose", "too short"), ("prose", None),
    ("prose", "x" * 50001), ("title", "   "), ("title", "t" * 201)],
    ids=["short-prose", "nontext-prose", "oversize-prose", "empty-title", "oversize-title"])
def test_history_rejects_invalid_prose_even_with_matching_projection_and_hash(history, field, value):
    from app.generation import digest
    from app.storage import AmbiguousWrite

    kernel, provider, book_id = history
    row, artifact = seed_final(kernel, book_id)
    payload = {**artifact, "content": {**artifact["content"], field: value}}
    payload["content_hash"] = digest(payload["content"])
    kernel.storage.update("artifacts", row["artifact_id"], {"payload_json": encode(payload)})
    kernel.storage.update("chapter_versions", row["version_id"], {"content_hash": payload["content_hash"],
        "content" if field == "prose" else "chapter_title": value})
    calls = list(provider.calls)
    with pytest.raises(AmbiguousWrite, match="Prior final chapter provenance"):
        kernel.story_planning.enqueue_brief(kernel.story_planning.brief_context(book_id, 2))
    assert provider.calls == calls and kernel.story_planning.list_briefs(book_id, 2) == []


@pytest.mark.parametrize("field,value", [("book_id", "wrong-book"), ("chapter_no", -1)])
def test_malformed_external_history_inventory_is_read_only_and_recoverable(history, monkeypatch, field, value):
    import httpx
    from app.storage import AmbiguousWrite

    kernel, provider, book_id = history
    row, _ = seed_final(kernel, book_id)
    mock = kernel.storage._repos["artifacts"]._client._http._transport
    original = mock.handler
    def malformed(request):
        response = original(request)
        if request.method == "GET" and request.url.path.endswith("/chapter_versions/records"):
            data = response.json()
            for item in data["data"]["items"]:
                item["fields"][field] = value
            return httpx.Response(200, json=data)
        return response
    monkeypatch.setattr(mock, "handler", malformed)
    calls, offset = list(provider.calls), len(original.calls)
    with pytest.raises(AmbiguousWrite, match="Invalid final chapter inventory"):
        kernel.story_planning.enqueue_brief(kernel.story_planning.brief_context(book_id, 2))
    assert_read_only(original, offset)
    assert provider.calls == calls
    monkeypatch.setattr(mock, "handler", original)
    assert kernel.storage.get("chapter_versions", row["version_id"]) == row
    assert kernel.story_planning.prior_final_chapters(book_id, 2)[0]["version_id"] == row["version_id"]


def test_planning_snapshot_cannot_drop_the_prior_final_reference(history):
    from app.storage import AmbiguousWrite

    kernel, provider, book_id = history
    seed_final(kernel, book_id)
    run = kernel.story_planning.enqueue_brief(kernel.story_planning.brief_context(book_id, 2))
    view = kernel.story_planning.read(run["pipeline_run_id"])
    snapshot = kernel.artifacts.get(view["snapshot_artifact_id"])
    kernel.storage.update("artifacts", snapshot["artifact_id"],
        {"payload_json": encode({**snapshot, "source_refs": snapshot["source_refs"][:2]})})
    calls = list(provider.calls)
    with pytest.raises(AmbiguousWrite, match="Planning snapshot history references changed"):
        kernel.story_planning.read(run["pipeline_run_id"])
    assert provider.calls == calls
    kernel.storage.update("artifacts", snapshot["artifact_id"], {"payload_json": encode(snapshot)})
    provider.outputs.append(brief())
    settle(kernel, 2)
    assert kernel.story_planning.read(run["pipeline_run_id"])["eligible"] is True
    assert provider.calls == [*calls, "chapter_planner"]
