"""
[INPUT]: Actual legacy WorkerLoop/PipelineEngine and mapped Feishu repositories; controlled external HTTP only.
[OUTPUT]: Domain/record identity, dependent execution, lease recovery and retry exhaustion contracts.
[POS]: Draft ZEN-104 compatibility integration tests; not the v0.2 scheduler or distributed safety proof.
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import copy
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest

from app.feishu.client import FeishuClient
from app.feishu.repositories.pipeline_runs import PipelineRunsRepo
from app.feishu.repositories.step_runs import StepRunsRepo
from app.pipeline.engine import PipelineEngine
from app.pipeline.models import StepDef
from app.pipeline.worker import WorkerLoop
from app.storage import DuplicateKey
from tests.feishu_transport import FeishuTransport


@pytest.fixture
def runtime():
    transport = FeishuTransport()
    client = FeishuClient("synthetic-worker-app", "synthetic-worker-secret")
    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(transport))
    pipelines = PipelineRunsRepo(client, "synthetic-base", "pipelines")
    steps = StepRunsRepo(client, "synthetic-base", "steps")
    engine = PipelineEngine(pipelines, steps, max_retries=1)
    worker = WorkerLoop(engine, "synthetic-worker", max_retries=1)
    run = engine.create_pipeline("compatibility", [
        StepDef("first", "synthetic-agent"),
        StepDef("second", "synthetic-agent", depends_on=("first",)),
    ])
    rows = steps.find_by_pipeline(run["pipeline_run_id"])
    yield SimpleNamespace(transport=transport, client=client, pipelines=pipelines,
        steps=steps, engine=engine, worker=worker, run=run, first=rows[0], second=rows[1])
    client._http.close()


def assert_record_paths(runtime):
    for call in runtime.transport.calls:
        if call.method in {"PUT", "DELETE"}:
            assert call.url.path.rsplit("/", 1)[-1].startswith("rec")
            assert runtime.run["pipeline_run_id"] not in call.url.path
            assert runtime.first["step_run_id"] not in call.url.path


def test_real_legacy_dependencies_claim_execute_and_finish_using_distinct_record_ids(runtime):
    calls = []
    first = runtime.worker.poll_once()
    assert first["record_id"] == runtime.first["record_id"]
    assert first["record_id"] != first["step_run_id"]
    assert first["lease_owner"] == "synthetic-worker"
    assert runtime.worker._resolve_record_id(first["step_run_id"]) == first["record_id"]
    assert runtime.pipelines.get(runtime.run["record_id"])["status"] == "running"

    def handler(step_id):
        calls.append(step_id)
        return {"output_refs": ["synthetic-artifact"]}

    completed = runtime.worker.execute_step(first["record_id"], handler)
    assert completed["status"] == "success"
    assert completed["output_refs"] == "synthetic-artifact"
    parent = runtime.pipelines.get(runtime.run["record_id"])
    assert parent["status"] == "running" and parent["current_step"] == "second"
    second = runtime.worker.poll_once()
    assert second["step_run_id"] == runtime.second["step_run_id"]

    def no_output(step_id):
        calls.append(step_id)

    assert runtime.worker.execute_step(second["record_id"], no_output)["status"] == "success"
    parent = runtime.pipelines.get(runtime.run["record_id"])
    assert parent["status"] == "completed" and parent["current_step"] == ""
    assert runtime.worker.poll_once() is None
    assert calls == [runtime.first["step_run_id"], runtime.second["step_run_id"]]
    assert len(runtime.transport.tables["pipelines"]) == 1
    assert len(runtime.transport.tables["steps"]) == 2
    assert_record_paths(runtime)


def test_real_legacy_retry_releases_lease_then_exhaustion_fails_parent_without_duplicate_rows(runtime):
    calls = []

    def failing(step_id):
        calls.append(step_id)
        raise RuntimeError("synthetic handler failure")

    claimed = runtime.worker.poll_once()
    requeued = runtime.worker.execute_step(claimed["record_id"], failing)
    assert requeued["status"] == "pending" and requeued["retry_count"] == 1
    assert requeued["lease_owner"] == requeued["lease_until"] == ""
    assert "RuntimeError: synthetic handler failure" in requeued["error_message"]
    assert runtime.pipelines.get(runtime.run["record_id"])["status"] == "running"
    claimed_again = runtime.worker.poll_once()
    assert claimed_again["record_id"] == claimed["record_id"]
    failed = runtime.worker.execute_step(claimed_again["record_id"], failing)
    assert failed["status"] == "failed" and failed["retry_count"] == 2
    assert runtime.pipelines.get(runtime.run["record_id"])["status"] == "failed"
    assert runtime.steps.get(runtime.second["record_id"])["status"] == "pending"
    assert runtime.worker.poll_once() is None
    assert calls == [runtime.first["step_run_id"]] * 2
    assert len(runtime.transport.tables["pipelines"]) == 1
    assert len(runtime.transport.tables["steps"]) == 2
    assert_record_paths(runtime)


@pytest.mark.parametrize("lookup", ["missing", "duplicate", "quoted"])
def test_actual_domain_resolution_refuses_missing_duplicate_and_literal_untrusted_ids(runtime, lookup):
    value = 'SR-unknown" || CurrentValue.[status] = "running' if lookup == "quoted" else "SR-absent"
    error = ValueError
    if lookup == "duplicate":
        value = runtime.first["step_run_id"]
        duplicate = copy.deepcopy(runtime.transport.tables["steps"][runtime.first["record_id"]])
        duplicate["record_id"] = "rec-duplicate"
        runtime.transport.tables["steps"]["rec-duplicate"] = duplicate
        error = DuplicateKey
    before = copy.deepcopy(runtime.transport.tables)
    start = len(runtime.transport.calls)
    with pytest.raises(error):
        runtime.worker._resolve_record_id(value)
    assert runtime.transport.tables == before
    calls = runtime.transport.calls[start:]
    assert len(calls) == 1 and calls[0].url.path.endswith("/records/search")
    assert json.loads(calls[0].content)["filter"] == {"conjunction": "or", "conditions": [
        {"field_name": "step_run_id", "operator": "is", "value": [value]}]}


@pytest.mark.parametrize("status", ["pending", "running"])
def test_another_workers_unexpired_lease_prevents_real_claim_and_poll_writes(runtime, status):
    deadline = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    runtime.steps.update(runtime.first["record_id"], {"status": status,
        "lease_owner": "other-worker", "lease_until": deadline})
    before = copy.deepcopy(runtime.transport.tables)
    start = len(runtime.transport.calls)
    with pytest.raises(RuntimeError, match="owned by other-worker"):
        runtime.worker.claim_step(runtime.first["record_id"])
    assert runtime.worker.poll_once() is None
    assert runtime.transport.tables == before
    assert all(call.method == "GET" or call.url.path.endswith("/records/search")
               for call in runtime.transport.calls[start:])


@pytest.mark.parametrize("deadline", ["missing", "invalid", "naive", "aware"])
def test_stale_running_lease_is_reclaimed_through_actual_repository(runtime, deadline):
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    value = {"missing": "", "invalid": "not-a-date", "naive": past.replace(tzinfo=None).isoformat(),
             "aware": past.isoformat()}[deadline]
    runtime.steps.update(runtime.first["record_id"], {"status": "running",
        "lease_owner": "old-worker", "lease_until": value})
    runtime.pipelines.update(runtime.run["record_id"], {"status": "running"})
    claimed = runtime.worker.poll_once()
    assert claimed["record_id"] == runtime.first["record_id"]
    assert claimed["status"] == "running" and claimed["lease_owner"] == "synthetic-worker"
    assert datetime.fromisoformat(claimed["lease_until"]) > datetime.now(timezone.utc)
    assert runtime.steps.get(runtime.first["record_id"])["lease_owner"] == "synthetic-worker"
    assert_record_paths(runtime)


def test_lease_expiring_during_actual_handler_prevents_completion_and_requeues_same_step(runtime):
    claimed = runtime.worker.poll_once()

    def handler(step_id):
        assert step_id == claimed["step_run_id"]
        # Change external state as if the time-bounded lease elapsed during the call.
        runtime.transport.tables["steps"][claimed["record_id"]]["fields"]["lease_until"] = (
            datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        return {"output_refs": ["must-not-be-committed"]}

    result = runtime.worker.execute_step(claimed["record_id"], handler)
    assert result["status"] == "pending" and result["retry_count"] == 1
    assert result["lease_owner"] == result["lease_until"] == ""
    assert "Lease expired" in result["error_message"]
    assert "output_refs" not in result
    assert runtime.steps.get(runtime.second["record_id"])["status"] == "pending"
    assert runtime.pipelines.get(runtime.run["record_id"])["status"] == "running"
    assert_record_paths(runtime)


def test_absent_physical_record_cannot_be_claimed(runtime):
    before = copy.deepcopy(runtime.transport.tables)
    start = len(runtime.transport.calls)
    with pytest.raises(ValueError, match="Step not found: rec-absent"):
        runtime.worker.claim_step("rec-absent")
    assert runtime.transport.tables == before
    assert len(runtime.transport.calls[start:]) == 1
    assert runtime.transport.calls[-1].method == "GET"


@pytest.mark.parametrize("damaged", ["parent_domain_id", "pending_record_id", "running_record_id"])
def test_incomplete_external_observations_cannot_be_claimed_or_written(runtime, damaged):
    if damaged == "parent_domain_id":
        runtime.transport.tables["pipelines"][runtime.run["record_id"]]["fields"].pop("pipeline_run_id")
    else:
        row = runtime.transport.tables["steps"][runtime.first["record_id"]]
        row["record_id"] = ""
        if damaged == "running_record_id":
            row["fields"].update(status="running", lease_owner="other-worker", lease_until="expired-invalid")
    before = copy.deepcopy(runtime.transport.tables)
    start = len(runtime.transport.calls)
    assert runtime.worker.poll_once() is None
    assert runtime.transport.tables == before
    assert all(call.method == "GET" for call in runtime.transport.calls[start:])


def test_external_stale_claim_write_failure_leaves_the_actual_step_and_parent_unchanged(runtime):
    row = runtime.transport.tables["steps"][runtime.first["record_id"]]
    row["fields"].update(status="running", lease_owner="old-worker", lease_until="expired-invalid")
    before = copy.deepcopy(runtime.transport.tables)
    actual_http = runtime.transport.__call__
    attempted = []

    def failed_put(outbound):
        if outbound.method == "PUT":
            attempted.append(outbound)
            return httpx.Response(400, json={"code": 123, "msg": "synthetic claim failure"})
        return actual_http(outbound)

    runtime.client._http.close()
    runtime.client._http = httpx.Client(transport=httpx.MockTransport(failed_put))
    assert runtime.worker.poll_once() is None
    assert runtime.transport.tables == before
    assert len(attempted) == 1
    assert attempted[0].url.path.endswith("/records/" + runtime.first["record_id"])


def test_engine_missing_step_and_parent_resolution_refuse_mutation(runtime):
    before = copy.deepcopy(runtime.transport.tables)
    start = len(runtime.transport.calls)
    with pytest.raises(ValueError, match="Step run not found: SR-absent"):
        runtime.engine.complete_step("SR-absent")
    # Explicit isolated parent-resolution contract, not a whole completion flow.
    with pytest.raises(ValueError, match="Pipeline run not found: PR-absent"):
        runtime.engine._update_pipeline("PR-absent", {"status": "completed"})
    assert runtime.transport.tables == before
    assert all(call.url.path.endswith("/records/search") for call in runtime.transport.calls[start:])


@pytest.mark.parametrize("expired", [False, True])
def test_actual_engine_normalizes_naive_lease_to_utc_before_completion(runtime, expired):
    deadline = datetime.now(timezone.utc) + timedelta(hours=-1 if expired else 1)
    runtime.steps.update(runtime.first["record_id"], {"status": "running",
        "lease_owner": "synthetic-worker", "lease_until": deadline.replace(tzinfo=None).isoformat()})
    before = copy.deepcopy(runtime.transport.tables)
    if expired:
        with pytest.raises(RuntimeError, match="Lease expired"):
            runtime.engine.complete_step(runtime.first["step_run_id"])
        assert runtime.transport.tables == before
    else:
        result = runtime.engine.complete_step(runtime.first["step_run_id"])
        assert result["status"] == "success"
        parent = runtime.pipelines.get(runtime.run["record_id"])
        assert parent["status"] == "running" and parent["current_step"] == "second"
    assert_record_paths(runtime)
