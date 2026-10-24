"""
[INPUT]: Actual review HTTP API/Kernel with externally duplicated Feishu projection state.
[OUTPUT]: Editorial commands refuse ambiguous source versions before durable decisions or revision intents.
[POS]: ZEN-41 regression; deterministic provider outputs prepare the source, not semantic acceptance.
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import copy
import json

import httpx
import pytest

from app.chapter_loop import ChapterLoopService
from app.harness import stable_id
from tests.test_chapter_loop import pass_run
from tests.test_chapter_review import chapter as chapter, target
from tests.test_chapter_projection_boundaries import HEADERS, api_for, raw_record, readonly, transport_of

pytest_plugins = ("tests.test_story_planning",)


@pytest.mark.parametrize("operation", ["decision", "revision"])
def test_editorial_command_refuses_projection_that_already_breaks_review_read(chapter, operation, tmp_path):
    kernel, provider, book_id = chapter
    view = pass_run(kernel, provider, book_id)
    command = target(view)
    transport = transport_of(kernel)
    _, original = raw_record(kernel, transport, "chapter_versions", "version_id", command["version_id"])
    fields = kernel.storage._repos["chapter_versions"]._field_map
    shadow = copy.deepcopy(original)
    shadow["record_id"] = "rec-external-editorial-duplicate"
    shadow["fields"].update({fields["version_id"]: "CV-" + "e" * 32,
                             fields["run_id"]: "PR-" + "e" * 32,
                             fields["status"]: "candidate"})
    transport.tables[kernel.storage._repos["chapter_versions"]._table_id][shadow["record_id"]] = shadow
    before, calls, model_calls = copy.deepcopy(transport.tables), len(transport.calls), list(provider.calls)
    if operation == "decision":
        command["action"] = "approve"
    else:
        command["constraints"] = {"must_change": ["Clarify the dialogue"]}
    api = api_for(kernel)
    try:
        path = f"/api/books/{book_id}/chapters/1"
        review = api.get(path + "/review", headers=HEADERS)
        assert review.status_code == 503, review.text
        response = api.post(path + "/review/" + operation, headers=HEADERS, json=command)
        (tmp_path / "editorial-duplicate-observation.json").write_text(json.dumps({
            "operation": operation, "review_status": review.status_code,
            "command_status": response.status_code, "command_body": response.json(),
            "before": before, "after": transport.tables,
            "model_calls_before": model_calls, "model_calls_after": provider.calls}, indent=2))
        assert response.status_code == 503, response.text
        assert response.json() == {"detail": "AmbiguousWrite", "reconciliation_required": True}
        assert transport.tables == before
        readonly(transport.calls[calls:])
        assert provider.calls == model_calls
    finally:
        api.close()


@pytest.mark.parametrize("operation", ["approve", "reject", "revision"])
@pytest.mark.parametrize("fault", ["foreign_duplicate", "same_run_duplicate", "missing_older_projection",
                                  "missing_older_artifact", "older_artifact_reference", "duplicate_artifact"])
def test_ambiguous_history_cannot_accept_editorial_commands_and_exact_restore_recovers(chapter, operation, fault):
    kernel, provider, book_id = chapter
    older = pass_run(kernel, provider, book_id)
    latest = pass_run(kernel, provider, book_id)
    command = target(latest)
    transport = transport_of(kernel)
    baseline = copy.deepcopy(transport.tables)
    cv_repo, ar_repo = kernel.storage._repos["chapter_versions"], kernel.storage._repos["artifacts"]
    old_version = target(older)
    cv_id, cv = raw_record(kernel, transport, "chapter_versions", "version_id", old_version["version_id"])
    ar_id, artifact = raw_record(kernel, transport, "artifacts", "artifact_id", old_version["artifact_id"])
    if fault in {"foreign_duplicate", "same_run_duplicate"}:
        shadow = copy.deepcopy(cv)
        shadow["record_id"] = "rec-external-editorial-history"
        shadow["fields"][cv_repo._field_map["version_id"]] = "CV-" + "e" * 32
        if fault == "foreign_duplicate":
            shadow["fields"][cv_repo._field_map["run_id"]] = "PR-" + "e" * 32
        transport.tables[cv_repo._table_id][shadow["record_id"]] = shadow
    elif fault == "missing_older_projection":
        del transport.tables[cv_repo._table_id][cv_id]
    elif fault == "missing_older_artifact":
        del transport.tables[ar_repo._table_id][ar_id]
    elif fault == "older_artifact_reference":
        cv["fields"][cv_repo._field_map["artifact_id"]] = "AR-other"
    else:
        shadow = copy.deepcopy(artifact)
        shadow["record_id"] = "rec-external-editorial-artifact"
        shadow["fields"][ar_repo._field_map["artifact_id"]] = "AR-" + "e" * 32
        transport.tables[ar_repo._table_id][shadow["record_id"]] = shadow
    if operation == "revision":
        command["constraints"] = {"must_change": ["Clarify the dialogue"]}
    else:
        command["action"] = operation
    path = f"/api/books/{book_id}/chapters/1/review/" + ("revision" if operation == "revision" else "decision")
    before, calls, model_calls = copy.deepcopy(transport.tables), len(transport.calls), list(provider.calls)
    api = api_for(kernel)
    try:
        refused = api.post(path, headers=HEADERS, json=command)
        assert refused.status_code == 503, refused.text
        assert refused.json() == {"detail": "AmbiguousWrite", "reconciliation_required": True}
        assert transport.tables == before
        readonly(transport.calls[calls:])
        assert provider.calls == model_calls
        transport.tables = copy.deepcopy(baseline)
        accepted = api.post(path, headers=HEADERS, json=command)
        assert accepted.status_code == (201 if operation == "revision" else 200), accepted.text
        if operation == "revision":
            assert accepted.json()["task"]["from_version_id"] == command["version_id"]
            assert accepted.json()["task"]["status"] == "queued"
        else:
            assert accepted.json()["decision"]["action"] == operation
            assert accepted.json()["version"]["status"] == ("approved" if operation == "approve" else "rejected")
        settled = copy.deepcopy(transport.tables)
        calls = len(transport.calls)
        replay = api.post(path, headers=HEADERS, json=command)
        assert replay.status_code == accepted.status_code and replay.json() == accepted.json()
        assert transport.tables == settled
        readonly(transport.calls[calls:])
        assert kernel.artifacts.get(older["selected"]["artifact_id"]) == older["selected"]
        assert kernel.artifacts.get(latest["selected"]["artifact_id"]) == latest["selected"]
        assert provider.calls == model_calls
    finally:
        api.close()


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_global_version_id_collision_outside_the_book_is_still_rejected(chapter, action):
    kernel, provider, book_id = chapter
    view = pass_run(kernel, provider, book_id)
    command = {**target(view), "action": action}
    transport = transport_of(kernel)
    baseline = copy.deepcopy(transport.tables)
    repo = kernel.storage._repos["chapter_versions"]
    _, row = raw_record(kernel, transport, "chapter_versions", "version_id", command["version_id"])
    shadow = copy.deepcopy(row)
    shadow["record_id"] = "rec-global-version-collision"
    shadow["fields"][repo._field_map["book_id"]] = "BK-unrelated-book"
    transport.tables[repo._table_id][shadow["record_id"]] = shadow
    before, calls, model_calls = copy.deepcopy(transport.tables), len(transport.calls), list(provider.calls)
    api = api_for(kernel)
    try:
        path = f"/api/books/{book_id}/chapters/1/review/decision"
        result = api.post(path, headers=HEADERS, json=command)
        assert result.status_code == 503 and result.json() == {
            "detail": "DuplicateKey", "reconciliation_required": True}
        assert transport.tables == before
        readonly(transport.calls[calls:])
        transport.tables = copy.deepcopy(baseline)
        recovered = api.post(path, headers=HEADERS, json=command)
        assert recovered.status_code == 200 and recovered.json()["decision"]["action"] == action
        assert provider.calls == model_calls
    finally:
        api.close()


@pytest.mark.parametrize("kwargs", [{"review_first_n": -1}, {"review_score_threshold": -1},
                                   {"review_score_threshold": 6}])
def test_invalid_review_policy_preserves_handlers_and_durable_state(chapter, kwargs):
    """Constructor boundary only; does not claim complete application startup."""
    kernel, provider, _ = chapter
    transport = transport_of(kernel)
    before, calls, model_calls = copy.deepcopy(transport.tables), len(transport.calls), list(provider.calls)
    handlers = dict(kernel.handlers)
    with pytest.raises(ValueError, match="Invalid chapter review policy"):
        ChapterLoopService(kernel, **kwargs)
    assert kernel.handlers == handlers and transport.tables == before
    assert len(transport.calls) == calls and provider.calls == model_calls


@pytest.mark.parametrize("field,value", [
    ("from_version_id", "CV-other"), ("source_artifact_id", "AR-other"),
    ("target_type", "another_target"), ("target_id", "BK-other/1"),
    ("created_by", "another-editor"), ("must_change", '["Unapproved change"]'),
])
def test_revision_replay_refuses_changed_durable_identity_and_restores_same_run(chapter, field, value):
    kernel, provider, book_id = chapter
    view = pass_run(kernel, provider, book_id)
    transport = transport_of(kernel)
    command = {**target(view), "constraints": {"must_change": ["Clarify the dialogue"]}}
    created = kernel.chapter_loop.request_revision(book_id, 1, **command)
    baseline = copy.deepcopy(transport.tables)
    repo = kernel.storage._repos["revision_tasks"]
    _, row = raw_record(kernel, transport, "revision_tasks", "revision_task_id", created["task"]["revision_task_id"])
    row["fields"][repo._field_map[field]] = value
    before, calls, model_calls = copy.deepcopy(transport.tables), len(transport.calls), list(provider.calls)
    api = api_for(kernel)
    try:
        path = f"/api/books/{book_id}/chapters/1/review/revision"
        refused = api.post(path, headers=HEADERS, json=command)
        assert refused.status_code == 409 and refused.json() == {
            "detail": "Revision replay does not match its source ChapterVersion"}
        assert transport.tables == before
        readonly(transport.calls[calls:])
        transport.tables = copy.deepcopy(baseline)
        calls = len(transport.calls)
        restored = api.post(path, headers=HEADERS, json=command)
        assert restored.status_code == 201 and restored.json() == created
        assert transport.tables == baseline
        readonly(transport.calls[calls:])
        assert kernel.artifacts.get(view["selected"]["artifact_id"]) == view["selected"]
        assert provider.calls == model_calls
    finally:
        api.close()


@pytest.mark.parametrize("boundary", ["source_gate", "queued_marker"])
def test_revision_recovers_exact_intent_after_remote_commit_and_unavailable_readback(chapter, boundary, tmp_path):
    kernel, provider, book_id = chapter
    kernel.chapter_loop = ChapterLoopService(kernel, review_first_n=1)
    view = pass_run(kernel, provider, book_id)
    assert view["run"]["status"] == "awaiting_approval"
    gate = next(s for s in view["run"]["steps"] if s["step_key"] == "final_verify")
    command = {**target(view), "expected_gate_version": gate["output_version"],
               "constraints": {"must_change": ["Clarify the dialogue"]}}
    task_id = stable_id("RT-", "chapter-revision/" + command["version_id"])
    transport = transport_of(kernel)
    client = kernel.storage._repos["artifacts"]._client._http
    collection = "step_runs" if boundary == "source_gate" else "revision_tasks"
    repo = kernel.storage._repos[collection]
    armed, blocked = [True], [False]
    fault_receipts = []
    before, model_calls = copy.deepcopy(transport.tables), list(provider.calls)

    def unavailable_readback(request):
        if blocked[0] and f"/tables/{repo._table_id}/records" in request.url.path:
            assert request.method == "GET" or request.url.path.endswith("/records/search")
            raise httpx.ReadTimeout("synthetic unavailable post-commit observation", request=request)

    def committed_response_lost(response):
        request = response.request
        if not armed[0] or request.method != "PUT" or f"/tables/{repo._table_id}/records/" not in request.url.path:
            return
        fields = json.loads(request.content)["fields"]
        target_status = "failed" if boundary == "source_gate" else "queued"
        if fields.get(repo._field_map["status"]) != target_status:
            return
        physical_id = request.url.path.rsplit("/", 1)[1]
        assert transport.tables[repo._table_id][physical_id]["fields"][repo._field_map["status"]] == target_status
        armed[0], blocked[0] = False, True
        fault_receipts.append({"physical_id": physical_id, "status_committed": target_status})
        raise httpx.ReadTimeout("synthetic response lost after remote commit", request=request)

    client.event_hooks["request"].append(unavailable_readback)
    client.event_hooks["response"].append(committed_response_lost)
    api = api_for(kernel)
    path = f"/api/books/{book_id}/chapters/1/review/revision"
    try:
        interrupted = api.post(path, headers=HEADERS, json=command)
        blocked[0] = False
        durable = kernel.storage.get("revision_tasks", task_id)
        after = copy.deepcopy(transport.tables)
        (tmp_path / "committed-revision-observation.json").write_text(json.dumps({
            "boundary": boundary, "status": interrupted.status_code, "body": interrupted.json(),
            "receipt": fault_receipts, "before": before, "after": after, "durable_task": durable}, indent=2))
        assert interrupted.status_code == 503 and interrupted.json() == {
            "detail": "AmbiguousWrite", "reconciliation_required": True}
        assert len(fault_receipts) == 1 and not armed[0]
        assert durable and durable["status"] == ("open" if boundary == "source_gate" else "queued")
        assert provider.calls == model_calls
        if boundary == "queued_marker":
            calls = len(transport.calls)
            stale = api.post(path, headers=HEADERS, json={**command, "expected_gate_version": 99})
            assert stale.status_code == 409 and stale.json() == {"detail": "Stale chapter review gate version"}
            assert transport.tables == after
            readonly(transport.calls[calls:])
        recovered = api.post(path, headers=HEADERS, json=command)
        assert recovered.status_code == 201, recovered.text
        queued = recovered.json()
        assert queued["task"]["revision_task_id"] == task_id and queued["task"]["status"] == "queued"
        assert queued["run"]["pipeline_run_id"] == durable["run_id"]
        assert len(kernel.storage.list("revision_tasks", book_id=book_id)) == 1
        assert len(kernel.storage.list("approval_events", target_id=gate["step_run_id"])) == 1
        assert len(kernel.chapter_loop.list_runs(book_id, 1)) == 2
        assert kernel.artifacts.get(view["selected"]["artifact_id"]) == view["selected"]
        settled, calls = copy.deepcopy(transport.tables), len(transport.calls)
        replay = api.post(path, headers=HEADERS, json=command)
        assert replay.status_code == 201 and replay.json() == queued
        assert transport.tables == settled
        readonly(transport.calls[calls:])
        assert provider.calls == model_calls and len(fault_receipts) == 1
    finally:
        blocked[0] = False
        client.event_hooks["request"].remove(unavailable_readback)
        client.event_hooks["response"].remove(committed_response_lost)
        api.close()


@pytest.mark.parametrize("operation", ["decision", "revision"])
def test_later_fresh_run_read_refuses_stale_initial_editorial_target(chapter, operation, tmp_path):
    kernel, provider, book_id = chapter
    old = pass_run(kernel, provider, book_id)
    newer = kernel.chapter_loop.enqueue(kernel.chapter_loop.context(book_id, 1))
    assert newer["status"] == "pending"
    transport = transport_of(kernel)
    client = kernel.storage._repos["pipeline_runs"]._client._http
    repo = kernel.storage._repos["pipeline_runs"]
    hidden = []

    def one_stale_run_response(response):
        req = response.request
        if hidden or req.method != "GET" or not req.url.path.endswith(f"/tables/{repo._table_id}/records"):
            return
        response.read()
        data = response.json()
        items = data["data"]["items"]
        removed = [row for row in items if row["fields"].get(repo._field_map["pipeline_run_id"]) == newer["pipeline_run_id"]]
        assert len(removed) == 1
        data["data"]["items"] = [row for row in items if row not in removed]
        response._content = json.dumps(data).encode()
        response.headers["content-length"] = str(len(response._content))
        hidden.append(newer["pipeline_run_id"])

    before, calls, model_calls = copy.deepcopy(transport.tables), len(transport.calls), list(provider.calls)
    client.event_hooks["response"].append(one_stale_run_response)
    command = target(old)
    command.update({"action": "approve"} if operation == "decision" else {
        "constraints": {"must_change": ["Clarify the dialogue"]}})
    api = api_for(kernel)
    try:
        response = api.post(f"/api/books/{book_id}/chapters/1/review/{operation}", headers=HEADERS, json=command)
        (tmp_path / "stale-run-observation.json").write_text(json.dumps({
            "operation": operation, "hidden_first_run": hidden, "actual_newer_run": newer["pipeline_run_id"],
            "status": response.status_code, "body": response.json(), "before": before,
            "after": transport.tables, "model_calls_before": model_calls,
            "model_calls_after": provider.calls}, indent=2))
        assert hidden == [newer["pipeline_run_id"]]
        assert response.status_code == 409 and response.json() == {
            "detail": "Review must name the current verified ChapterVersion"}
        assert transport.tables == before
        readonly(transport.calls[calls:])
        assert provider.calls == model_calls
    finally:
        client.event_hooks["response"].remove(one_stale_run_response)
        api.close()


@pytest.mark.parametrize("field", ["content_hash", "review_report_id", "verifier_artifact_id"])
@pytest.mark.parametrize("operation", ["approve", "reject", "revision"])
def test_projection_provenance_rejected_by_review_cannot_be_consumed_by_command(chapter, field, operation, tmp_path):
    kernel, provider, book_id = chapter
    view = pass_run(kernel, provider, book_id)
    command = target(view)
    transport = transport_of(kernel)
    baseline = copy.deepcopy(transport.tables)
    repo = kernel.storage._repos["chapter_versions"]
    _, row = raw_record(kernel, transport, "chapter_versions", "version_id", command["version_id"])
    row["fields"][repo._field_map[field]] = "changed-hash" if field == "content_hash" else command["artifact_id"]
    before, calls, model_calls = copy.deepcopy(transport.tables), len(transport.calls), list(provider.calls)
    command.update({"constraints": {"must_change": ["Clarify the dialogue"]}} if operation == "revision" else {
        "action": operation})
    api = api_for(kernel)
    path = f"/api/books/{book_id}/chapters/1"
    suffix = "/review/" + ("revision" if operation == "revision" else "decision")
    try:
        unreadable = api.get(path + "/review", headers=HEADERS)
        assert unreadable.status_code == 503, unreadable.text
        refused = api.post(path + suffix, headers=HEADERS, json=command)
        (tmp_path / "editorial-provenance-observation.json").write_text(json.dumps({
            "field": field, "operation": operation, "read_status": unreadable.status_code,
            "command_status": refused.status_code, "body": refused.json(), "before": before,
            "after": transport.tables, "model_calls_before": model_calls,
            "model_calls_after": provider.calls}, indent=2))
        assert refused.status_code == 503, refused.text
        assert refused.json() == {"detail": "AmbiguousWrite", "reconciliation_required": True}
        assert transport.tables == before
        readonly(transport.calls[calls:])
        transport.tables = copy.deepcopy(baseline)
        accepted = api.post(path + suffix, headers=HEADERS, json=command)
        assert accepted.status_code == (201 if operation == "revision" else 200), accepted.text
        assert kernel.artifacts.get(view["selected"]["artifact_id"]) == view["selected"]
        assert provider.calls == model_calls
    finally:
        api.close()
