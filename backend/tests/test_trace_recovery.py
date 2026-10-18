"""A restarted observer must not report old attempts as still executing."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.generation import (ArtifactStore, CallContext, Completion, ModelRouter,
                            Prompt, Route, SemanticRuntime, TraceRecorder)
from app.harness import HarnessKernel
from app.main import create_app
from app.storage import AmbiguousWrite
from tests.test_model_foundations import foundation as foundation, Output


class ProcessStopped(BaseException):
    """The process died without executing an exception/finally path."""


def trace_writes(transport, offset):
    return [request for request in transport.calls[offset:]
            if request.method in {"PUT", "DELETE"} or request.method == "POST"
            and not request.url.path.endswith("/records/search")]


def test_restart_closes_old_agent_attempt_without_repeating_model_or_artifact(foundation):
    kernel, trace, artifacts = foundation
    kernel.telemetry = trace
    model_calls, attempts, outputs = [], [], []

    class Provider:
        def complete(self, route, messages):
            model_calls.append(messages)
            return Completion('{"summary":"preserved result"}', "resolved", 12, 7)

    def register(target):
        target.telemetry = TraceRecorder(target)
        store = ArtifactStore(target)
        router = ModelRouter({"r": Route(provider="deepseek", model="configured")},
                             {"deepseek": Provider()}, target.telemetry)
        semantic = SemanticRuntime(router, store)

        def handler(step):
            artifact = semantic.execute(route="r", prompt=Prompt(version="1", template="JSON"),
                inputs={"summary": "source"}, input_schema=Output, output_schema=Output,
                context=CallContext(run_id=step["pipeline_run_id"], step_id=step["step_run_id"]),
                logical_id="same-paid-result", version=1, artifact_type="Test")
            outputs.append(artifact)
            attempts.append(step["step_run_id"])
            if len(attempts) == 1:
                raise ProcessStopped()
            return {"output_refs": [artifact["artifact_id"]]}

        target.register("generate", handler)

    register(kernel)
    run_id = kernel.create("same-request", "recovery", [
        {"step_key": "generate", "handler": "generate", "kind": "agent"}])["pipeline_run_id"]
    with pytest.raises(ProcessStopped):
        kernel.tick()
    before = kernel.telemetry.list(run_id=run_id)
    original_model = next(row for row in before if row["kind"] == "model")
    original_agent = next(row for row in before if row["kind"] == "agent")
    assert original_agent["status"] == "running" and original_model["status"] == "success"
    restarted = HarnessKernel(kernel.storage, journal_dir=kernel.journal.directory)
    register(restarted)
    restarted.recover()
    restarted.tick()
    final = restarted.get(run_id)
    assert final["status"] == "completed" and final["steps"][0]["retry_count"] == 1
    assert len(model_calls) == 1 and len(attempts) == 2 and attempts[0] == attempts[1]
    assert outputs[0] == outputs[1] == artifacts.get(outputs[0]["artifact_id"])
    after = restarted.telemetry.list(run_id=run_id)
    assert next(row for row in after if row["kind"] == "model") == original_model
    recovered = next(row for row in after if row["trace_id"] == original_agent["trace_id"])
    assert recovered == {**original_agent, "status": "interrupted", "failure_class": "Interrupted",
                         "outcome_unknown": True, "finished_at": recovered["finished_at"]}
    assert recovered["finished_at"] >= recovered["created_at"]
    assert [row["status"] for row in after if row["kind"] == "agent"] == ["interrupted", "success"]
    with TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=restarted)) as api:
        path = f"/api/workflows/{run_id}/trace"
        assert api.get(path).status_code == 401
        response = api.get(path, headers={"x-api-key": "test"})
        assert response.status_code == 200 and response.json() == after
    assert not restarted.running and len(model_calls) == 1


def test_unknown_model_usage_remains_unknown_and_repeated_recovery_is_read_only(foundation):
    kernel, trace, _ = foundation
    kernel.telemetry = trace
    pending = trace.start({"kind": "model", "run_id": "old", "step_id": "step", "attempt": 0})
    done = trace.start({"kind": "model", "run_id": "old", "step_id": "other", "attempt": 0})
    trace.finish(done, status="success", input_tokens=10, output_tokens=5, estimated_cost=0.1)
    previous = next(row for row in trace.list() if row["trace_id"] == done)
    failed = trace.start({"kind": "model", "run_id": "failed-run", "step_id": "other", "attempt": 0})
    trace.finish(failed, status="failed", failure_class="SchemaFailure", input_tokens=8, output_tokens=3)
    failed_before = next(row for row in trace.list() if row["trace_id"] == failed)
    kernel.recover()
    result = {row["trace_id"]: row for row in trace.list()}
    assert result[done] == previous
    assert result[failed] == failed_before
    assert result[pending]["status"] == "interrupted" and result[pending]["outcome_unknown"] is True
    assert result[pending]["input_tokens"] is result[pending]["output_tokens"] is None
    assert result[pending]["estimated_cost"] is None
    usage = trace.usage(run_id="old")
    assert usage["attempts"] == 2 and usage["unknown_usage_attempts"] == 1
    assert usage["input_tokens"] is usage["output_tokens"] is usage["estimated_cost"] is None
    transport = kernel.storage._repos["traces"]._client._http._transport.handler
    offset = len(transport.calls)
    kernel.recover()
    assert {row["trace_id"]: row for row in trace.list()} == result
    assert not trace_writes(transport, offset)


@pytest.mark.parametrize("fault", ["json", "non_object", "id", "kind", "run", "step", "chapter",
                                 "status", "missing_status", "non_string_status"])
def test_corrupt_trace_stops_recovery_before_any_trace_mutation(foundation, fault):
    kernel, trace, _ = foundation
    kernel.telemetry = trace
    first = trace.start({"kind": "agent", "run_id": "run", "step_id": "step"})
    second = trace.start({"kind": "model", "run_id": "run", "step_id": "step"})
    original = {row["trace_id"]: row for row in kernel.storage.list("traces")}
    payload = json.loads(original[second]["payload_json"])
    if fault == "json":
        corrupt = "{"
    elif fault == "non_object":
        corrupt = "[]"
    elif fault == "missing_status":
        del payload["status"]
        corrupt = json.dumps(payload)
    elif fault == "non_string_status":
        payload["status"] = {}
        corrupt = json.dumps(payload)
    else:
        field = {"id": "trace_id", "kind": "kind", "run": "run_id", "step": "step_id",
                 "chapter": "chapter_id", "status": "status"}[fault]
        payload[field] = "foreign-value"
        corrupt = json.dumps(payload)
    kernel.storage.update("traces", second, {"payload_json": corrupt})
    transport = kernel.storage._repos["traces"]._client._http._transport.handler
    offset = len(transport.calls)
    with pytest.raises(AmbiguousWrite, match="Invalid persisted trace during recovery"):
        kernel.recover()
    assert kernel.storage.get("traces", first) == original[first]
    assert kernel.storage.get("traces", second)["payload_json"] == corrupt
    assert not trace_writes(transport, offset)
    assert not kernel.running


def test_trace_update_failure_stops_startup_and_exact_recovery_retries_safely(foundation, monkeypatch):
    kernel, trace, _ = foundation
    kernel.telemetry = trace
    tid = trace.start({"kind": "agent", "run_id": "old", "step_id": "step"})
    update = kernel.storage.update

    def fail(collection, domain_id, fields):
        if collection == "traces":
            raise RuntimeError("transport unavailable")
        return update(collection, domain_id, fields)

    try:
        monkeypatch.setattr(kernel.storage, "update", fail)
        with pytest.raises(RuntimeError, match="transport unavailable"):
            kernel.start()
        assert not kernel.running and trace.list()[0]["status"] == "running"
        monkeypatch.setattr(kernel.storage, "update", update)
        kernel.recover()
        assert trace.list()[0]["trace_id"] == tid and trace.list()[0]["status"] == "interrupted"
        assert kernel.storage.list("pipeline_runs") == []
    finally:
        kernel.stop()


def test_recovery_update_committed_before_timeout_is_reconciled_without_second_write(foundation):
    kernel, trace, _ = foundation
    kernel.telemetry = trace
    tid = trace.start({"kind": "model", "run_id": "old", "step_id": "step"})
    client = kernel.storage._repos["traces"]._client
    transport = client._http._transport.handler
    writes = []

    def timeout_after_commit(request):
        response = transport(request)
        if request.method == "PUT" and "/tables/traces/records/" in request.url.path:
            writes.append(request)
            raise httpx.ReadTimeout("response lost", request=request)
        return response

    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(timeout_after_commit))
    kernel.recover()
    result = trace.list()[0]
    assert result["trace_id"] == tid and result["status"] == "interrupted"
    assert result["input_tokens"] is result["output_tokens"] is None
    assert len(writes) == 1
    kernel.recover()
    assert trace.list()[0] == result and len(writes) == 1
