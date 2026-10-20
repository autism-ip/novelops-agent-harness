"""
[INPUT]: Actual Harness/API and stateful Feishu HTTP fixture.
[OUTPUT]: Approval identity, transition and startup boundary guarantees.
[POS]: ZEN-104 regression tests; no business-method replacements or live calls.
[PROTOCOL]: Update this header when changing the contract, then check CLAUDE.md.
"""
import copy

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.test_harness_kernel import runtime as runtime

HEADERS = {"x-api-key": "test"}


def api_for(kernel):
    return TestClient(create_app(Settings(_env_file=None, BACKEND_API_KEY="test"), kernel=kernel))


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
