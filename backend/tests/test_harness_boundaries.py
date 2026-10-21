"""
[INPUT]: Actual Harness/API and stateful Feishu HTTP fixture.
[OUTPUT]: Typed approval identity, exact replay and recovery guarantees.
[POS]: ZEN-104 regression tests; no business-method replacements or live calls.
[PROTOCOL]: Update this header when changing the contract, then check CLAUDE.md.
"""
import copy

import pytest
from fastapi.testclient import TestClient
from app.harness import HarnessKernel, stable_id
from app.feishu.table_map import FIELD_MAPS
from app.storage import AmbiguousWrite

from app.config import Settings
from app.main import create_app
from tests.test_harness_kernel import runtime as runtime

HEADERS = {"x-api-key": "test"}


def api_for(kernel):
    return TestClient(create_app(Settings(_env_file=None, BACKEND_API_KEY="test"), kernel=kernel),
                      raise_server_exceptions=False)


def assert_only_reads(transport):
    assert transport.calls
    assert all(r.method == "GET" or r.method == "POST" and r.url.path.endswith("/records/search")
               for r in transport.calls)


def approval_gate(runtime, action):
    kernel, storage, transport, _ = runtime
    calls = []
    kernel.register("boundary", lambda step: calls.append(step["step_run_id"]) or {"result": "ready"})
    run = kernel.create("approval-identity-"+action, "boundary", [
        {"step_key": "review", "handler": "boundary", "requires_approval": True}])
    kernel.tick()
    step = kernel.get(run["pipeline_run_id"])["steps"][0]
    assert step["status"] == "awaiting_approval" and calls == [step["step_run_id"]]
    # The real table exists; prime the HTTP fixture's lazy empty container before
    # freezing the no-mutation baseline. Preserve the whole-state assertion.
    assert storage.list("approval_events") == []
    return step, calls


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_changed_operator_is_not_an_exact_approval_replay(runtime, action):
    kernel, storage, transport, _ = runtime
    step, calls = approval_gate(runtime, action)
    body = {"action": action, "expected_version": 1, "operator": "original-editor"}
    with api_for(kernel) as api:
        # Drive the kernel deterministically before entering the client context;
        # after completion its scheduler has no pending external business effect.
        path = f"/api/workflows/steps/{step['step_run_id']}/decision"
        response = api.post(path, headers=HEADERS, json=body)
        assert response.status_code == 200
        baseline = copy.deepcopy(transport.tables)
        transport.calls.clear()
        changed = api.post(path, headers=HEADERS, json={**body, "operator": "different-editor"})
        assert changed.status_code == 409
        assert transport.tables == baseline
        assert_only_reads(transport)
        assert api.post(path, headers=HEADERS, json=body).status_code == 200
        assert transport.tables == baseline
        assert_only_reads(transport)
    assert calls == [step["step_run_id"]]
    events = storage.list("approval_events")
    assert len(events) == 1 and events[0]["operator"] == "original-editor"
    assert events[0]["action"] == action


@pytest.mark.parametrize("action", ["approve", "reject"])
@pytest.mark.parametrize("operator", [" ", "\t\n"])
def test_whitespace_operator_cannot_commit_an_approval(runtime, action, operator):
    kernel, storage, transport, _ = runtime
    step, calls = approval_gate(runtime, action)
    baseline = copy.deepcopy(transport.tables)
    transport.calls.clear()
    api = api_for(kernel)
    try:
        path = f"/api/workflows/steps/{step['step_run_id']}/decision"
        body = {"action": action, "expected_version": 1, "operator": operator}
        response = api.post(path, headers=HEADERS, json=body)
        assert response.status_code == 422
        assert transport.tables == baseline
        assert not transport.calls or all(r.method == "GET" or r.method == "POST"
            and r.url.path.endswith("/records/search") for r in transport.calls)
        valid = api.post(path, headers=HEADERS, json={**body, "operator": "editor"})
        assert valid.status_code == 200
    finally:
        api.close()
    events = storage.list("approval_events")
    assert len(events) == 1 and events[0]["operator"] == "editor"
    assert calls == [step["step_run_id"]]


class SimulatedProcessCrash(BaseException):
    """Stop after the actual external event commit, before step settlement."""


@pytest.mark.parametrize("stage", ["event_committed", "settled"])
@pytest.mark.parametrize("action", ["approve", "reject"])
@pytest.mark.parametrize("fault", ["target_type", "target_id", "target_version",
                                   "missing_type", "missing_id", "missing_version",
                                   "action", "missing_action", "operator", "missing_operator"])
def test_corrupt_approval_target_cannot_settle_or_replay_and_restores_exactly(runtime, stage, action, fault):
    kernel, storage, transport, journal = runtime
    step, calls = approval_gate(runtime, action)
    client = storage._repos["approval_events"]._client._http
    if stage == "event_committed":
        def crash_after_commit(response):
            req = response.request
            if req.method == "POST" and "/tables/approval_events/" in req.url.path and req.url.path.endswith("/records"):
                raise SimulatedProcessCrash()
        client.event_hooks["response"].append(crash_after_commit)
        try:
            with pytest.raises(SimulatedProcessCrash):
                kernel.decide(step["step_run_id"], action, 1, "original-editor")
        finally:
            client.event_hooks["response"].remove(crash_after_commit)
        assert storage.get("step_runs", step["step_run_id"])["status"] == "awaiting_approval"
    else:
        kernel.decide(step["step_run_id"], action, 1, "original-editor")
    approval_id = stable_id("AP-", step["step_run_id"]+"/1")
    original_event = storage.get("approval_events", approval_id)
    assert original_event["target_type"] == "step_run"
    assert original_event["target_id"] == step["step_run_id"] and original_event["target_version"] == 1
    original = copy.deepcopy(transport.tables)
    fields = next(row["fields"] for row in transport.tables["approval_events"].values()
                  if row["fields"][FIELD_MAPS["approval_events"]["approval_id"]] == approval_id)
    field = {"missing_type": "target_type", "missing_id": "target_id",
             "missing_version": "target_version", "missing_action": "action",
             "missing_operator": "operator"}.get(fault, fault)
    key = FIELD_MAPS["approval_events"][field]
    if fault.startswith("missing_"):
        fields.pop(key)
    else:
        fields[key] = {"target_type": "chapter_version", "target_id": "SR-other-step",
                       "target_version": 2, "action": "unsupported", "operator": " "}[field]
    damaged = copy.deepcopy(transport.tables)
    transport.calls.clear()
    api = api_for(kernel)
    try:
        path = f"/api/workflows/steps/{step['step_run_id']}/decision"
        body = {"action": action, "expected_version": 1, "operator": "original-editor"}
        response = api.post(path, headers=HEADERS, json=body)
        assert response.status_code == 503
        assert response.json() == {"detail": "AmbiguousWrite", "reconciliation_required": True}
        assert transport.tables == damaged
        assert_only_reads(transport)
        if stage == "event_committed":
            restarted = HarnessKernel(storage, journal_dir=journal)
            with pytest.raises(AmbiguousWrite, match="approval"):
                restarted.recover()
            assert transport.tables == damaged
            assert_only_reads(transport)
        transport.tables = original
        if stage == "event_committed":
            restarted.recover()
        baseline = copy.deepcopy(transport.tables)
        transport.calls.clear()
        restored = api.post(path, headers=HEADERS, json=body)
        assert restored.status_code == 200
        assert restored.json()["status"] == ("success" if action == "approve" else "failed")
        assert transport.tables == baseline
        assert_only_reads(transport)
    finally:
        api.close()
    assert calls == [step["step_run_id"]]
    assert storage.list("approval_events") == [original_event]


@pytest.mark.parametrize("expected_version", [True, "1", 1.0])
def test_approval_version_requires_a_json_integer_before_storage(runtime, expected_version):
    kernel, _, transport, _ = runtime
    step, calls = approval_gate(runtime, "approve")
    baseline = copy.deepcopy(transport.tables)
    transport.calls.clear()
    api = api_for(kernel)
    try:
        response = api.post(f"/api/workflows/steps/{step['step_run_id']}/decision", headers=HEADERS,
            json={"action": "approve", "expected_version": expected_version, "operator": "editor"})
        assert response.status_code == 422
        assert transport.tables == baseline and not transport.calls
    finally:
        api.close()
    assert calls == [step["step_run_id"]]


@pytest.mark.parametrize("expected_version", [True, "1", 1.0, None, 0])
def test_core_approval_version_fails_before_storage(runtime, expected_version):
    kernel, _, transport, _ = runtime
    step, calls = approval_gate(runtime, "approve")
    baseline = copy.deepcopy(transport.tables)
    transport.calls.clear()
    with pytest.raises(ValueError, match="positive integer"):
        kernel.decide(step["step_run_id"], "approve", expected_version, "editor")
    assert transport.tables == baseline and not transport.calls
    assert calls == [step["step_run_id"]]


@pytest.mark.parametrize("operator", [None, 0, []])
def test_core_approval_operator_is_text_before_storage(runtime, operator):
    kernel, _, transport, _ = runtime
    step, calls = approval_gate(runtime, "approve")
    baseline = copy.deepcopy(transport.tables)
    transport.calls.clear()
    with pytest.raises(ValueError, match="Operator is required"):
        kernel.decide(step["step_run_id"], "approve", 1, operator)
    assert transport.tables == baseline and not transport.calls
    assert calls == [step["step_run_id"]]
