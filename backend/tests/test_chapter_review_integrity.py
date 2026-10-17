"""Editorial commands must fail closed when durable sources are stale or corrupt."""
import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.test_chapter_review import chapter as chapter, target
from tests.test_chapter_loop import pass_run

pytest_plugins = ("tests.test_story_planning",)


def api_for(kernel):
    # Synchronous commands only: no scheduler races with the deliberate remote faults.
    return TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))


def assert_read_only(transport, offset):
    assert all(request.method == "GET" or request.method == "POST"
               and request.url.path.endswith("/records/search")
               for request in transport.calls[offset:])


@pytest.mark.parametrize("operation", ["decision", "revision", "final-lock"])
def test_whitespace_editor_is_rejected_without_side_effects(chapter, operation):
    kernel, provider, book_id = chapter
    view = pass_run(kernel, provider, book_id)
    command = {**target(view), "operator": "   "}
    if operation == "decision":
        suffix = "/review/decision"
        command["action"] = "approve"
    elif operation == "revision":
        suffix = "/review/revision"
        command["constraints"] = {"must_change": ["Tighten dialogue"]}
    else:
        suffix = "/final-lock"
        command.pop("run_id")
    transport = kernel.storage._repos["artifacts"]._client._http._transport.handler
    offset, model_calls = len(transport.calls), list(provider.calls)
    api = api_for(kernel)
    try:
        result = api.post(f"/api/books/{book_id}/chapters/1" + suffix,
                          headers={"x-api-key": "test"}, json=command)
        assert result.status_code == 422
        assert result.json() == {"detail": "Operator is required"}
        assert_read_only(transport, offset)
        assert provider.calls == model_calls
    finally:
        api.close()


@pytest.mark.parametrize("fault,detail", [
    ("content_hash", "ChapterVersion projection provenance changed"),
    ("review_report_id", "ChapterVersion review report provenance changed"),
    ("verifier_artifact_id", "ChapterVersion verifier provenance changed"),
])
def test_history_rejects_tampered_projection_and_recovers(chapter, fault, detail):
    kernel, provider, book_id = chapter
    view = pass_run(kernel, provider, book_id)
    command = target(view)
    original = kernel.storage.get("chapter_versions", command["version_id"])
    changed = "corrupt-hash" if fault == "content_hash" else view["selected"]["artifact_id"]
    kernel.storage.update("chapter_versions", command["version_id"], {fault: changed})
    transport = kernel.storage._repos["artifacts"]._client._http._transport.handler
    offset, model_calls = len(transport.calls), list(provider.calls)
    api = api_for(kernel)
    path = f"/api/books/{book_id}/chapters/1/versions"
    try:
        result = api.get(path, headers={"x-api-key": "test"})
        assert result.status_code == 503
        assert result.json() == {"detail": "AmbiguousWrite", "reconciliation_required": True}
        # Also check the domain diagnosis; HTTP intentionally exposes only the safe class.
        from app.storage import AmbiguousWrite
        with pytest.raises(AmbiguousWrite, match=detail):
            kernel.chapter_loop.versions(book_id, 1)
        assert_read_only(transport, offset)
        assert provider.calls == model_calls
        kernel.storage.update("chapter_versions", command["version_id"], {fault: original[fault]})
        restored = api.get(path, headers={"x-api-key": "test"})
        assert restored.status_code == 200
        assert restored.json()[0]["artifact"] == view["selected"]
        assert restored.json()[0]["record"] == original
    finally:
        api.close()


@pytest.mark.parametrize("fault,detail", [
    ("unreadable_request", "frozen request is unreadable"),
    ("changed_request", "frozen request does not match the exact command"),
    ("missing_run", "Queued revision run is missing"),
    ("invalid_status", "status is not replayable"),
    ("unresolved_source_gate", "before its source gate resolved"),
])
def test_revision_replay_does_not_recreate_or_execute_ambiguous_intent(chapter, fault, detail):
    kernel, provider, book_id = chapter
    view = pass_run(kernel, provider, book_id)
    command = {**target(view), "constraints": {"must_keep": ["Mira"],
        "must_change": ["Sharper dialogue"], "do_not_change": []}}
    queued = kernel.chapter_loop.request_revision(book_id, 1, **command)
    task = queued["task"]
    if fault == "unreadable_request":
        kernel.storage.update("revision_tasks", task["revision_task_id"], {"request_json": "{"})
    elif fault == "changed_request":
        request = json.loads(task["request_json"])
        request["constraints"]["must_change"] = ["An unapproved different instruction"]
        kernel.storage.update("revision_tasks", task["revision_task_id"], {"request_json": json.dumps(request)})
    elif fault == "missing_run":
        kernel.storage.delete("pipeline_runs", task["run_id"])
    elif fault == "invalid_status":
        kernel.storage.update("revision_tasks", task["revision_task_id"], {"status": "unrecognized"})
    else:
        gate = next(s for s in view["run"]["steps"] if s["step_key"] == "final_verify")
        kernel.storage.update("step_runs", gate["step_run_id"], {"status": "pending"})
    transport = kernel.storage._repos["artifacts"]._client._http._transport.handler
    offset, model_calls = len(transport.calls), list(provider.calls)
    api = api_for(kernel)
    try:
        result = api.post(f"/api/books/{book_id}/chapters/1/review/revision",
                          headers={"x-api-key": "test"}, json=command)
        assert result.status_code == 503
        assert result.json() == {"detail": "AmbiguousWrite", "reconciliation_required": True}
        from app.storage import AmbiguousWrite
        with pytest.raises(AmbiguousWrite, match=detail):
            kernel.chapter_loop.request_revision(book_id, 1, **command)
        assert_read_only(transport, offset)
        assert provider.calls == model_calls
        assert len(kernel.storage.list("revision_tasks", book_id=book_id)) == 1
    finally:
        api.close()


def test_final_lock_replay_is_read_only_and_binds_editor_and_artifact(chapter):
    kernel, provider, book_id = chapter
    view = pass_run(kernel, provider, book_id)
    command = {key: value for key, value in target(view).items() if key != "run_id"}
    api = api_for(kernel)
    path = f"/api/books/{book_id}/chapters/1/final-lock"
    headers = {"x-api-key": "test"}
    try:
        first = api.post(path, headers=headers, json=command)
        assert first.status_code == 200 and first.json()["status"] == "final"
        transport = kernel.storage._repos["artifacts"]._client._http._transport.handler
        offset, model_calls = len(transport.calls), list(provider.calls)
        replay = api.post(path, headers=headers, json=command)
        assert replay.status_code == 200 and replay.json() == first.json()
        for change in ({"operator": "another-editor"}, {"artifact_id": "AR-other"}, {"version_no": 99}):
            conflict = api.post(path, headers=headers, json={**command, **change})
            assert conflict.status_code == 409
            assert conflict.json() == {"detail": "A different ChapterVersion is already final-locked"}
        assert_read_only(transport, offset)
        assert provider.calls == model_calls
        assert kernel.artifacts.get(command["artifact_id"]) == view["selected"]
        assert kernel.storage.get("chapter_versions", command["version_id"]) == first.json()
    finally:
        api.close()


@pytest.mark.parametrize("fault,endpoint,expected_status,detail", [
    ("missing_projection", "/review/decision", 409, "ChapterVersion projection changed"),
    ("changed_projection", "/review/decision", 409, "ChapterVersion projection changed"),
    ("unfinished_run", "/review/decision", 409, "Chapter run is not ready for editorial review"),
    ("stale_decision_gate", "/review/decision", 409, "Stale chapter review gate version"),
    ("stale_revision_gate", "/review/revision", 409, "Stale chapter review gate version"),
    ("no_change_request", "/review/revision", 422, "Revision needs an explicit must_change constraint"),
    ("rejected_source", "/review/revision", 409, "Only a current review ChapterVersion can be revised"),
    ("unstarted_chapter", "/final-lock", 409, "Latest chapter run is not completed"),
    ("changed_verifier", "/final-lock", 409, "ChapterVersion is not ready for final lock"),
    ("wrong_final_version", "/final-lock", 409, "Final lock must name the current verified ChapterVersion"),
])
def test_editorial_preconditions_fail_before_durable_command(chapter, fault, endpoint, expected_status, detail):
    kernel, provider, book_id = chapter
    view = pass_run(kernel, provider, book_id)
    command = target(view)
    chapter_no = 1
    if fault == "missing_projection":
        kernel.storage.delete("chapter_versions", command["version_id"])
    elif fault == "changed_projection":
        kernel.storage.update("chapter_versions", command["version_id"], {"artifact_id": "AR-other"})
    elif fault == "unfinished_run":
        gate = next(s for s in view["run"]["steps"] if s["step_key"] == "final_verify")
        kernel.storage.update("step_runs", gate["step_run_id"], {"status": "failed"})
        kernel.storage.update("pipeline_runs", command["run_id"], {"status": "failed"})
    elif fault.startswith("stale_"):
        command["expected_gate_version"] = 99
    elif fault == "rejected_source":
        rejected = kernel.chapter_loop.decide_review(book_id, 1, **command, action="reject")
        assert rejected["version"]["status"] == "rejected"
    elif fault == "unstarted_chapter":
        chapter_no = 2
    elif fault == "changed_verifier":
        kernel.storage.update("chapter_versions", command["version_id"], {"verifier_artifact_id": "AR-other"})
    elif fault == "wrong_final_version":
        command["version_no"] = 99
    if endpoint == "/review/decision":
        command["action"] = "approve"
    elif endpoint == "/review/revision":
        command["constraints"] = {"must_change": [] if fault == "no_change_request" else ["Sharper dialogue"]}
    else:
        command.pop("run_id")
    transport = kernel.storage._repos["artifacts"]._client._http._transport.handler
    offset, model_calls = len(transport.calls), list(provider.calls)
    api = api_for(kernel)
    try:
        result = api.post(f"/api/books/{book_id}/chapters/{chapter_no}" + endpoint,
                          headers={"x-api-key": "test"}, json=command)
        assert result.status_code == expected_status, result.text
        assert result.json() == {"detail": detail}
        assert_read_only(transport, offset)
        assert provider.calls == model_calls
        assert kernel.storage.list("revision_tasks", book_id=book_id) == []
        assert kernel.artifacts.get(view["selected"]["artifact_id"]) == view["selected"]
    finally:
        api.close()
