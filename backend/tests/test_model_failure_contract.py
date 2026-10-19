"""Model failures and successful provenance must come from this exact call."""
import json

import httpx
import pytest

from app.generation import (ChatProvider, ModelFailure, ModelRouter, Prompt, Route,
                            SemanticRuntime)
from app.storage import AmbiguousWrite, MissingRecord
from tests.test_model_foundations import foundation as foundation, Output, context


def artifact_args():
    return dict(logical_id="failure-contract", version=1, artifact_type="ContractTest",
        content={"summary": "validated"}, context=context(), prompt=Prompt(version="1", template="JSON"),
        route="r", provider="deepseek", model="resolved")


@pytest.mark.parametrize("history", ["missing", "stale"])
def test_semantic_generation_uses_current_committed_trace_without_history_scan(foundation, history):
    kernel, trace, artifacts = foundation
    old_id = trace.start({"kind": "model", "run_id": "run", "step_id": "step", "model": "old-model"})
    trace.finish(old_id, status="success", output_refs=["older-artifact"])
    old_trace = trace.list(run_id="run")[0]
    db_client = kernel.storage._repos["traces"]._client
    transport = db_client._http._transport.handler
    hide_history, history_reads = [True], []

    def incomplete_history(request):
        response = transport(request)
        if hide_history[0] and request.method == "GET" and request.url.path.endswith("/tables/traces/records"):
            history_reads.append(request)
            data = response.json()
            if history == "missing":
                data["data"]["items"] = []
            else:
                data["data"]["items"] = [row for row in data["data"]["items"]
                    if row["fields"]["trace_id"] == old_id]
            return httpx.Response(200, json=data)
        return response

    db_client._http.close()
    db_client._http = httpx.Client(transport=httpx.MockTransport(incomplete_history))
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"model": "current-model", "choices": [{"finish_reason": "stop",
            "message": {"content": '{"summary":"current result"}'}}],
            "usage": {"prompt_tokens": 13, "completion_tokens": 7}})

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        router = ModelRouter({"r": Route(provider="deepseek", model="configured-alias", max_retries=0)},
            {"deepseek": ChatProvider("deepseek", "test-key", client=http)}, trace)
        semantic = SemanticRuntime(router, artifacts)
        args = dict(route="r", prompt=Prompt(version="1", template="JSON"), inputs={"summary": "source"},
            input_schema=Output, output_schema=Output, context=context(), logical_id="current-artifact",
            version=1, artifact_type="ContractTest")
        artifact = semantic.execute(**args)
        hide_history[0] = False
        after = trace.list(run_id="run")
        assert artifact["model"] == "current-model"
        assert not history_reads, "A successful call must not rediscover its provenance through history"
        assert next(row for row in after if row["trace_id"] == old_id) == old_trace
        new = [row for row in after if row["trace_id"] != old_id]
        assert len(new) == 1 and new[0]["model"] == artifact["model"]
        assert artifact["model_trace_id"] == new[0]["trace_id"]
        assert new[0]["output_refs"] == [artifact["artifact_id"]]
        assert semantic.execute(**args) == artifact and len(calls) == 1


def test_exact_replay_repairs_trace_link_after_artifact_commit_without_another_model_call(foundation):
    kernel, trace, artifacts = foundation
    db_client = kernel.storage._repos["traces"]._client
    transport = db_client._http._transport.handler
    reject_link = [True]

    def fail_link(request):
        if reject_link[0] and request.method == "PUT" and "/tables/traces/records/" in request.url.path:
            body = json.loads(request.content)
            payload = json.loads(body["fields"]["payload_json"])
            if payload.get("output_refs"):
                return httpx.Response(503)
        return transport(request)

    db_client._http.close()
    db_client._http = httpx.Client(transport=httpx.MockTransport(fail_link))
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"model": "resolved", "choices": [{"finish_reason": "stop",
            "message": {"content": '{"summary":"already persisted"}'}}]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        router = ModelRouter({"r": Route(provider="deepseek", model="configured", max_retries=0)},
            {"deepseek": ChatProvider("deepseek", "test-key", client=http)}, trace)
        semantic = SemanticRuntime(router, artifacts)
        args = dict(route="r", prompt=Prompt(version="1", template="JSON"), inputs={},
            input_schema=dict_schema(), output_schema=Output, context=context(), logical_id="link-recovery",
            version=1, artifact_type="ContractTest")
        with pytest.raises(AmbiguousWrite):
            semantic.execute(**args)
        saved = kernel.storage.list("artifacts")
        assert len(saved) == 1 and len(calls) == 1 and trace.list(run_id="run")[0]["output_refs"] == []
        original = artifacts.get(saved[0]["artifact_id"])
        reject_link[0] = False
        replay = semantic.execute(**args)
        assert replay == original and len(calls) == 1
        model_trace = trace.list(run_id="run")[0]
        assert model_trace["output_refs"] == [replay["artifact_id"]]
        assert replay["model_trace_id"] == model_trace["trace_id"]
        assert semantic.execute(**args) == replay and trace.list(run_id="run")[0] == model_trace


@pytest.mark.parametrize("retries", [0, 1, 2])
def test_retry_exhaustion_is_bounded_and_never_returns_a_missing_output(foundation, retries):
    _, trace, _ = foundation
    requests, sleeps = [], []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(429, text="private provider response")

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        router = ModelRouter({"r": Route(provider="deepseek", model="configured", max_retries=retries)},
            {"deepseek": ChatProvider("deepseek", "test-key", client=http)}, trace, sleep=sleeps.append)
        with pytest.raises(ModelFailure, match="RateLimited"):
            router.generate("r", Prompt(version="1", template="JSON"), {}, Output, context())
    assert len(requests) == retries + 1 and all(body == requests[0] for body in requests)
    assert sleeps == [0.2 * 2 ** attempt for attempt in range(retries)]
    rows = trace.list(run_id="run")
    assert [row["attempt"] for row in rows] == list(range(retries + 1))
    assert len({row["call_id"] for row in rows}) == 1
    assert all(row["status"] == "failed" and row["failure_class"] == "RateLimited" for row in rows)
    assert "private provider response" not in json.dumps(rows)


@pytest.mark.parametrize("first_failure", ["schema", "rate_limit"])
def test_retry_links_only_the_successful_attempt_to_the_artifact(foundation, first_failure):
    _, trace, artifacts = foundation
    calls = []

    def respond(request):
        calls.append(request)
        if len(calls) == 1 and first_failure == "rate_limit":
            return httpx.Response(429)
        content = '{"wrong":"schema"}' if len(calls) == 1 else '{"summary":"final result"}'
        return httpx.Response(200, json={"model": "first-model" if len(calls) == 1 else "final-model",
            "choices": [{"finish_reason": "stop", "message": {"content": content}}],
            "usage": {"prompt_tokens": 13, "completion_tokens": 7}})

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        router = ModelRouter({"r": Route(provider="deepseek", model="configured", max_retries=1)},
            {"deepseek": ChatProvider("deepseek", "test-key", client=http)}, trace, sleep=lambda _: None)
        artifact = SemanticRuntime(router, artifacts).execute(route="r",
            prompt=Prompt(version="1", template="JSON"), inputs={}, input_schema=dict_schema(),
            output_schema=Output, context=context(), logical_id="retried", version=1,
            artifact_type="ContractTest")
    rows = trace.list(run_id="run")
    assert len(calls) == 2 and len(rows) == 2 and artifact["model"] == "final-model"
    assert rows[0]["status"] == "failed" and rows[0]["output_refs"] == []
    assert rows[1]["status"] == "success" and rows[1]["model"] == artifact["model"]
    assert rows[1]["output_refs"] == [artifact["artifact_id"]]
    assert rows[0]["call_id"] == rows[1]["call_id"]
    usage = trace.usage(run_id="run")
    assert usage["attempts"] == 2 and usage["retries"] == 1
    assert usage["input_tokens"] == (26 if first_failure == "schema" else None)


def test_unsupported_provider_never_allocates_a_client(monkeypatch):
    clients = []
    monkeypatch.setattr(httpx, "Client", lambda: clients.append(True))
    with pytest.raises(ValueError, match="Unsupported model provider"):
        ChatProvider("unknown", "test-key")
    assert not clients


def test_closing_provider_keeps_borrowed_client_open():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as http:
        provider = ChatProvider("openai", "test-key", client=http)
        provider.close()
        assert not http.is_closed
    assert http.is_closed


@pytest.mark.parametrize("provider", ["deepseek", "openai"])
def test_connection_failures_are_bounded_sanitized_and_usage_unknown(foundation, provider):
    kernel, trace, _ = foundation
    requests = []

    def fail(request):
        requests.append(request)
        raise httpx.ConnectError("private connection details", request=request)

    with httpx.Client(transport=httpx.MockTransport(fail)) as http:
        router = ModelRouter({"r": Route(provider=provider, model="configured", max_retries=1)},
            {provider: ChatProvider(provider, "test-key", client=http)}, trace, sleep=lambda _: None)
        with pytest.raises(ModelFailure, match="TransportFailure"):
            router.generate("r", Prompt(version="1", template="JSON"), {}, Output, context())
    rows = trace.list(run_id="run")
    assert len(requests) == 2 and len(rows) == 2
    assert all(row["status"] == "failed" and row["failure_class"] == "TransportFailure" for row in rows)
    assert "private connection details" not in json.dumps(rows)
    usage = trace.usage(run_id="run")
    assert usage["unknown_usage_attempts"] == 2 and usage["input_tokens"] is usage["output_tokens"] is None
    assert kernel.storage.list("artifacts") == []


@pytest.mark.parametrize("content", [None, [], {}, 42])
def test_non_text_provider_output_cannot_become_an_artifact(foundation, content):
    kernel, trace, artifacts = foundation
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
        "choices": [{"finish_reason": "stop", "message": {"content": content}}]}))) as http:
        router = ModelRouter({"r": Route(provider="deepseek", model="configured", max_retries=0)},
            {"deepseek": ChatProvider("deepseek", "test-key", client=http)}, trace)
        semantic = SemanticRuntime(router, artifacts)
        with pytest.raises(ModelFailure, match="MalformedResponse"):
            semantic.execute(route="r", prompt=Prompt(version="1", template="JSON"), inputs={},
                input_schema=dict_schema(), output_schema=Output, context=context(), logical_id="invalid",
                version=1, artifact_type="ContractTest")
    assert kernel.storage.list("artifacts") == []
    assert trace.list(run_id="run")[0]["failure_class"] == "MalformedResponse"


def dict_schema():
    from pydantic import BaseModel

    class EmptyInput(BaseModel):
        pass

    return EmptyInput


def test_missing_adapter_has_one_failed_attempt_and_no_artifact(foundation):
    kernel, trace, _ = foundation
    router = ModelRouter({"r": Route(provider="deepseek", model="configured")}, {}, trace)
    with pytest.raises(ModelFailure, match="MissingConfiguration"):
        router.generate("r", Prompt(version="1", template="JSON"), {}, Output, context())
    rows = trace.list(run_id="run")
    assert len(rows) == 1 and rows[0]["failure_class"] == "MissingConfiguration"
    assert kernel.storage.list("artifacts") == []


def test_semantic_missing_route_rejects_without_model_or_storage_writes(foundation):
    kernel, trace, artifacts = foundation
    semantic = SemanticRuntime(ModelRouter({}, {}, trace), artifacts)
    transport = kernel.storage._repos["artifacts"]._client._http._transport.handler
    offset = len(transport.calls)
    with pytest.raises(ModelFailure, match="MissingRoute"):
        semantic.execute(route="missing", prompt=Prompt(version="1", template="JSON"), inputs={},
            input_schema=dict_schema(), output_schema=Output, context=context(), logical_id="invalid",
            version=1, artifact_type="ContractTest")
    assert transport.calls[offset:] == []


def test_missing_trace_finish_does_not_upsert_an_observation(foundation):
    kernel, trace, _ = foundation
    with pytest.raises(MissingRecord, match="TR-missing"):
        trace.finish("TR-missing", status="success")
    assert kernel.storage.list("traces") == []


@pytest.mark.parametrize("changed", [{"version": 0}, {"logical_id": ""}, {"artifact_type": ""}])
def test_invalid_artifact_identity_is_rejected_before_remote_read(foundation, changed):
    kernel, _, artifacts = foundation
    transport = kernel.storage._repos["artifacts"]._client._http._transport.handler
    offset = len(transport.calls)
    with pytest.raises(ValueError, match="Artifact type, logical ID and positive version required"):
        artifacts.save(**{**artifact_args(), **changed})
    assert transport.calls[offset:] == []


def test_conflicting_create_echo_is_not_accepted_or_reposted(foundation):
    kernel, _, artifacts = foundation
    client = kernel.storage._repos["artifacts"]._client
    transport = client._http._transport.handler
    creates = []

    def change_echo(request):
        response = transport(request)
        if request.method == "POST" and request.url.path.endswith("/tables/artifacts/records"):
            creates.append(request)
            data = response.json()
            payload = json.loads(data["data"]["record"]["fields"]["payload_json"])
            payload["model"] = "unconfirmed-other-model"
            data["data"]["record"]["fields"]["payload_json"] = json.dumps(payload)
            return httpx.Response(200, json=data)
        return response

    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(change_echo))
    with pytest.raises(ValueError, match="Artifact version is immutable"):
        artifacts.save(**artifact_args())
    assert len(creates) == 1
    # The real committed record is unchanged; reconcile the exact command safely.
    replay = artifacts.save(**artifact_args())
    assert replay["model"] == "resolved" and len(creates) == 1


@pytest.fixture
def generated(foundation):
    kernel, trace, artifacts = foundation
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"model": "resolved", "choices": [{"finish_reason": "stop",
            "message": {"content": '{"summary":"stable result"}'}}]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        router = ModelRouter({"r": Route(provider="deepseek", model="configured", max_retries=0)},
            {"deepseek": ChatProvider("deepseek", "test-key", client=http)}, trace)
        semantic = SemanticRuntime(router, artifacts)
        args = dict(route="r", prompt=Prompt(version="1", template="JSON"), inputs={},
            input_schema=dict_schema(), output_schema=Output, context=context(), logical_id="preserved",
            version=1, artifact_type="ContractTest")
        artifact = semantic.execute(**args)
        yield kernel, trace, artifacts, semantic, args, artifact, calls


@pytest.mark.parametrize("legacy", ["absent", "empty"])
def test_legacy_artifact_shape_remains_readable_without_guessing_a_trace_or_writing(generated, legacy):
    kernel, trace, artifacts, semantic, args, artifact, calls = generated
    payload = dict(artifact)
    del payload["model_trace_id"]
    expected = dict(payload)
    if legacy == "empty":
        payload["model_trace_id"] = ""
    raw = json.dumps(payload)
    kernel.storage.update("artifacts", artifact["artifact_id"], {"payload_json": raw})
    original_trace = trace.list(run_id="run")
    transport = kernel.storage._repos["artifacts"]._client._http._transport.handler
    offset = len(transport.calls)
    assert artifacts.get(artifact["artifact_id"]) == expected
    assert semantic.execute(**args) == expected and len(calls) == 1
    assert kernel.storage.get("artifacts", artifact["artifact_id"])["payload_json"] == raw
    assert trace.list(run_id="run") == original_trace
    assert not [r for r in transport.calls[offset:] if r.method in {"PUT", "DELETE"}
                or r.method == "POST" and r.url.path.endswith("/records")]


def test_missing_confirmed_trace_blocks_exact_replay_without_regeneration(generated):
    kernel, _, artifacts, semantic, args, artifact, calls = generated
    kernel.storage.delete("traces", artifact["model_trace_id"])
    with pytest.raises(AmbiguousWrite, match="Artifact model trace is missing"):
        semantic.execute(**args)
    assert len(calls) == 1 and artifacts.get(artifact["artifact_id"]) == artifact


@pytest.mark.parametrize("fault", ["json", "non_object", "row_identity", "model", "output_hash",
    "input_refs", "status", "route_hash", "prompt_hash", "prompt_version", "workflow_version",
    "chapter_id", "provider", "other_output_refs"])
def test_wrong_trace_provenance_cannot_be_relinked_or_regenerated(generated, fault):
    kernel, _, artifacts, semantic, args, artifact, calls = generated
    trace_id = artifact["model_trace_id"]
    row = kernel.storage.get("traces", trace_id)
    payload = json.loads(row["payload_json"])
    if fault == "json":
        fields = {"payload_json": "{"}
    elif fault == "non_object":
        fields = {"payload_json": "[]"}
    elif fault == "row_identity":
        fields = {"step_id": "other-step"}
    else:
        key = "output_refs" if fault == "other_output_refs" else fault
        payload[key] = ["other-artifact"] if key in {"input_refs", "output_refs"} else "other-value"
        fields = {"payload_json": json.dumps(payload)}
    kernel.storage.update("traces", trace_id, fields)
    corrupt = kernel.storage.get("traces", trace_id)
    transport = kernel.storage._repos["traces"]._client._http._transport.handler
    offset = len(transport.calls)
    with pytest.raises(AmbiguousWrite, match="Artifact model trace provenance changed"):
        semantic.execute(**args)
    assert len(calls) == 1 and artifacts.get(artifact["artifact_id"]) == artifact
    assert kernel.storage.get("traces", trace_id) == corrupt
    assert not [r for r in transport.calls[offset:] if r.method in {"PUT", "DELETE"}
                or r.method == "POST" and r.url.path.endswith("/records")]
    kernel.storage.update("traces", trace_id, {k: row.get(k, "") for k in fields})
    assert semantic.execute(**args) == artifact and len(calls) == 1
