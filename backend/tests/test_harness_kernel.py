"""Runtime acceptance through actual Feishu client/repository composition."""
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.harness import HarnessKernel, TransitionConflict
from app.main import create_app
from tests.feishu_transport import make_storage


@pytest.fixture
def runtime(tmp_path):
    storage, transport, client = make_storage()
    kernel = HarnessKernel(storage, journal_dir=tmp_path, poll_interval=0.01, max_retries=1)
    yield kernel, storage, transport, tmp_path
    kernel.stop()
    client._http.close()


def definition(gate=False):
    return [{"step_key": "collect", "handler": "noop", "kind": "tool", "requires_approval": gate},
            {"step_key": "save", "handler": "noop", "kind": "service", "depends_on": ["collect"]}]


def test_lifespan_runs_enqueued_work_and_shutdown_stops(runtime):
    kernel, storage, _, _ = runtime
    app = create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel)
    with TestClient(app) as client:
        response = client.post("/api/workflows", headers={"x-api-key": "test"}, json={
            "request_key": "one", "workflow_type": "test", "steps": definition()})
        assert response.status_code == 201, response.text
        run_id = response.json()["pipeline_run_id"]
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            run = client.get(f"/api/workflows/{run_id}", headers={"x-api-key": "test"}).json()
            if run["status"] == "completed":
                break
            time.sleep(0.01)
        assert run["status"] == "completed"
        assert all(s["status"] == "success" for s in run["steps"])
        assert client.get("/api/system/status").json()["worker_status"] == "running"
        assert client.get("/api/workflows").status_code == 401
    assert not kernel.running


def test_replay_and_changed_request_conflict(runtime):
    kernel, storage, _, _ = runtime
    run = kernel.create("stable", "test", definition())
    assert kernel.create("stable", "test", definition()) == run
    assert len(storage.list("pipeline_runs")) == 1
    assert len(storage.list("step_runs")) == 2
    with pytest.raises(TransitionConflict):
        kernel.create("stable", "changed", definition())


def test_approval_is_versioned_idempotent_and_resumes(runtime):
    kernel, storage, _, _ = runtime
    run = kernel.create("gate", "test", definition(True))
    kernel.tick()
    step = kernel.get(run["pipeline_run_id"])["steps"][0]
    assert step["status"] == "awaiting_approval"
    with pytest.raises(TransitionConflict):
        kernel.decide(step["step_run_id"], "approve", 99, "operator")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: kernel.decide(step["step_run_id"], "approve", 1, "operator"), range(2)))
    assert results[0]["status"] == results[1]["status"] == "success"
    assert len(storage.list("approval_events")) == 1
    with pytest.raises(TransitionConflict):
        kernel.decide(step["step_run_id"], "reject", 1, "operator")
    kernel.tick()
    assert kernel.get(run["pipeline_run_id"])["status"] == "completed"


def test_tool_failures_retry_bounded_and_parent_fails(runtime):
    kernel, _, _, _ = runtime
    calls = []
    def fail(step):
        calls.append(step["step_run_id"])
        raise RuntimeError("provider secret must not appear in API")
    kernel.register("bad", fail)
    run = kernel.create("failure", "test", [{"step_key": "bad", "handler": "bad", "kind": "tool"}])
    for _ in range(5):
        kernel.tick()
    result = kernel.get(run["pipeline_run_id"])
    assert result["status"] == "failed"
    assert len(calls) == 2
    assert "secret" not in str(result)


def test_restart_recovers_running_step_with_stable_identity(runtime):
    kernel, storage, _, journal = runtime
    run = kernel.create("restart", "test", definition())
    step = kernel.get(run["pipeline_run_id"])["steps"][0]
    storage.update("step_runs", step["step_run_id"], {"status": "running"})
    restarted = HarnessKernel(storage, journal_dir=journal, max_retries=1)
    restarted.recover()
    restarted.tick()
    restarted.tick()
    assert restarted.get(run["pipeline_run_id"])["status"] == "completed"


def test_partial_creation_recovers_existing_but_never_reposts_unknown(runtime):
    kernel, storage, transport, journal = runtime
    transport.fail_create = "step_runs"
    with pytest.raises(Exception):
        kernel.create("partial", "test", definition())
    posts_before = len([r for r in transport.calls if r.method == "POST"])
    restarted = HarnessKernel(storage, journal_dir=journal)
    restarted.recover()
    run = storage.list("pipeline_runs")[0]
    assert run["status"] == "blocked"
    assert len([r for r in transport.calls if r.method == "POST"]) == posts_before


def test_terminal_and_dependency_transitions_are_guarded(runtime):
    kernel, _, _, _ = runtime
    run = kernel.create("cancel", "test", definition())
    kernel.cancel(run["pipeline_run_id"])
    kernel.tick()
    assert kernel.get(run["pipeline_run_id"])["status"] == "cancelled"
    with pytest.raises(ValueError):
        kernel.create("cycle", "test", [{"step_key": "a", "handler": "noop", "depends_on": ["a"]}])


def test_real_production_composition_and_api_errors(runtime, monkeypatch, tmp_path):
    _, storage, transport, _ = runtime
    import httpx
    from app.feishu.client import FeishuClient
    from app import runtime as composition
    client = FeishuClient("app", "secret")
    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(transport))
    monkeypatch.setattr(composition, "FeishuClient", lambda *_: client)
    monkeypatch.setenv("FEISHU_APP_TOKEN", "app")
    for name in ("pipeline_runs", "step_runs", "approval_events"):
        monkeypatch.setenv("FEISHU_TABLE_ID_" + name.upper(), name)
    settings = Settings(BACKEND_API_KEY="test", HARNESS_ENABLED=True,
                        HARNESS_JOURNAL_DIR=str(tmp_path / "production"), HARNESS_POLL_INTERVAL=0.01)
    with TestClient(create_app(settings)) as api:
        headers = {"x-api-key": "test"}
        assert api.get("/api/workflows/missing", headers=headers).status_code == 404
        body = {"request_key": "compose", "workflow_type": "test", "steps": definition(True)}
        created = api.post("/api/workflows", headers=headers, json=body)
        assert created.status_code == 201
        assert api.get("/api/workflows", headers=headers).json()
        body["workflow_type"] = "changed"
        assert api.post("/api/workflows", headers=headers, json=body).status_code == 409
        body["steps"][0]["handler"] = "unregistered"
        assert api.post("/api/workflows", headers=headers, json=body).status_code == 422
        run_id = created.json()["pipeline_run_id"]
        assert api.post(f"/api/workflows/{run_id}/cancel", headers=headers).status_code == 200
        assert api.post("/api/pipelines", headers=headers, json={"pipeline_type":"legacy", "steps":[]}).status_code == 410


def test_fail_fast_missing_configuration_and_disabled_api(tmp_path, monkeypatch):
    from app.runtime import build_runtime
    monkeypatch.delenv("FEISHU_APP_TOKEN", raising=False)
    with pytest.raises(ValueError, match="FEISHU_APP_TOKEN"):
        build_runtime(Settings(BACKEND_API_KEY="test"))
    with TestClient(create_app(Settings(BACKEND_API_KEY="test"))) as client:
        assert client.get("/api/workflows", headers={"x-api-key":"test"}).status_code == 503


def test_second_scheduler_cannot_acquire_writer_lock(runtime):
    kernel, storage, _, journal = runtime
    kernel.start()
    second = HarnessKernel(storage, journal_dir=journal)
    with pytest.raises(BlockingIOError):
        second.start()
    assert kernel.running


def test_ambiguous_handler_stops_without_retry(runtime):
    from app.storage import AmbiguousWrite
    kernel, _, _, _ = runtime
    calls = []
    def ambiguous(step):
        calls.append(step)
        raise AmbiguousWrite("unknown external create")
    kernel.register("ambiguous", ambiguous)
    run = kernel.create("ambiguous", "test", [{"step_key":"x", "handler":"ambiguous"}])
    kernel.tick()
    kernel.tick()
    assert len(calls) == 1
    assert kernel.get(run["pipeline_run_id"])["status"] == "blocked"


def test_approval_recovers_crash_after_event_persisted(runtime):
    from app.harness import stable_id
    kernel, storage, _, journal = runtime
    run = kernel.create("approve-restart", "test", definition(True))
    kernel.tick()
    step = kernel.get(run["pipeline_run_id"])["steps"][0]
    storage.ensure("approval_events", {"approval_id": stable_id("AP-", step["step_run_id"] + "/1"),
        "target_id": step["step_run_id"], "target_version": 1, "action": "approve", "operator": "test"})
    restarted = HarnessKernel(storage, journal_dir=journal)
    restarted.recover()
    restarted.tick()
    assert restarted.get(run["pipeline_run_id"])["status"] == "completed"


def test_scheduler_stops_on_completion_persistence_failure(runtime, monkeypatch):
    from app.feishu.client import FeishuAPIError
    kernel, storage, _, _ = runtime
    run = kernel.create("persist-failure", "test", definition())
    original = storage.update
    def fail(collection, domain_id, fields):
        if fields.get("status") == "success":
            raise FeishuAPIError("secret response", code=503)
        return original(collection, domain_id, fields)
    monkeypatch.setattr(storage, "update", fail)
    kernel.start()
    deadline = time.monotonic() + 2
    while kernel.running and time.monotonic() < deadline:
        time.sleep(0.01)
    assert kernel.last_error == "FeishuAPIError"
    assert not kernel.running


def test_runnable_order_does_not_depend_on_storage_order(runtime, monkeypatch):
    kernel, storage, _, _ = runtime
    calls = []
    kernel.register("record", lambda step: calls.append(step["step_key"]))
    kernel.create("order", "test", [
        {"step_key": key, "handler": "record"} for key in ("a", "b", "c")])
    original = storage.list
    monkeypatch.setattr(storage, "list", lambda *a, **kw: list(reversed(original(*a, **kw))))
    for _ in range(3):
        kernel.tick()
    assert calls == ["a", "b", "c"]


@pytest.mark.parametrize("blocked", [False, True])
def test_failed_parent_terminalizes_siblings_and_rejects_decision(runtime, blocked):
    from app.storage import AmbiguousWrite
    kernel, storage, _, journal = runtime
    kernel.max_retries = 0
    def fail(step):
        raise AmbiguousWrite("unknown") if blocked else RuntimeError("failed")
    kernel.register("fail", fail)
    run = kernel.create("siblings", "test", [
        {"step_key": "a", "handler": "noop", "requires_approval": True},
        {"step_key": "b", "handler": "fail"},
        {"step_key": "c", "handler": "noop", "depends_on": ["a"]}])
    kernel.tick()
    kernel.tick()
    result = kernel.get(run["pipeline_run_id"])
    assert result["status"] == ("blocked" if blocked else "failed")
    assert [s["status"] for s in result["steps"]] == ["cancelled", result["status"], "cancelled"]
    with pytest.raises(TransitionConflict):
        kernel.decide(result["steps"][0]["step_run_id"], "approve", 1, "operator")
    # A crash/old deployment may leave siblings nonterminal under a terminal parent.
    storage.update("step_runs", result["steps"][2]["step_run_id"], {"status": "pending"})
    restarted = HarnessKernel(storage, journal_dir=journal)
    restarted.recover()
    assert restarted.get(run["pipeline_run_id"])["steps"][2]["status"] == "cancelled"


def test_invalid_result_blocks_without_repeating_external_effect(runtime):
    kernel, storage, _, journal = runtime
    calls = []
    kernel.register("invalid", lambda step: calls.append(step) or {"bad": object()})
    run = kernel.create("invalid", "test", [{"step_key": "a", "handler": "invalid"}])
    kernel.tick()
    restarted = HarnessKernel(storage, journal_dir=journal)
    restarted.register("invalid", kernel.handlers["invalid"])
    restarted.recover()
    restarted.tick()
    result = restarted.get(run["pipeline_run_id"])
    assert result["status"] == "blocked"
    assert result["steps"][0]["retry_count"] == 0
    assert len(calls) == 1


def test_missing_handler_blocks_without_consuming_execution_retry(runtime):
    kernel, _, _, _ = runtime
    kernel.register("removed", lambda step: {})
    run = kernel.create("removed", "test", [{"step_key": "a", "handler": "removed"}])
    del kernel.handlers["removed"]
    kernel.tick()
    result = kernel.get(run["pipeline_run_id"])
    assert result["status"] == "blocked"
    assert result["steps"][0]["retry_count"] == 0


def test_status_reads_no_remote_tables_and_tracks_lifecycle(runtime):
    kernel, _, transport, _ = runtime
    run = kernel.create("status", "test", definition())
    before = len(transport.calls)
    for _ in range(5):
        status = kernel.status()
        assert status["active_pipeline_runs"] == 1
        assert status["pending_steps"] == 2
    assert len(transport.calls) == before
    kernel.cancel(run["pipeline_run_id"])
    assert kernel.status()["active_pipeline_runs"] == 0
    assert kernel.status()["pending_steps"] == 0
