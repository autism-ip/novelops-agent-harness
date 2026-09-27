import json

import httpx
import pytest
from pydantic import BaseModel

from app.generation import (ArtifactStore, CallContext, ChatProvider, ModelRouter,
                            Prompt, Route, ModelFailure, TraceRecorder)
from app.harness import HarnessKernel
from tests.feishu_transport import make_storage


class Output(BaseModel):
    summary: str


@pytest.fixture
def foundation(tmp_path):
    storage, transport, client = make_storage()
    kernel = HarnessKernel(storage, journal_dir=tmp_path)
    trace = TraceRecorder(kernel)
    yield kernel, trace, ArtifactStore(kernel)
    client._http.close()


def context():
    return CallContext(run_id="run", step_id="step", chapter_id="book:1", input_refs=("source@1",))


@pytest.mark.parametrize("provider", ["openai", "deepseek"])
def test_provider_contract_validates_schema_and_records_usage(provider, foundation):
    kernel, trace, _ = foundation
    def respond(request):
        assert request.headers["authorization"] == "Bearer secret"
        body = json.loads(request.content)
        assert body["response_format"] == {"type":"json_object"}
        return httpx.Response(200, json={"model":"configured-model", "choices":[{"message":{"content":'{"summary":"ok"}'}}],
                                         "usage":{"prompt_tokens":100,"completion_tokens":50}})
    http = httpx.Client(transport=httpx.MockTransport(respond))
    router = ModelRouter({"research": Route(provider=provider, model="configured-model", input_cost_per_million=1, output_cost_per_million=2)},
                         {provider:ChatProvider(provider,"secret",client=http)}, trace, sleep=lambda _:None)
    result = router.generate("research", Prompt(version="v1", template="Summarize"), {}, Output, context())
    assert result.summary == "ok"
    usage = trace.usage(run_id="run")
    assert usage["input_tokens"] == 100
    assert usage["estimated_cost"] == pytest.approx(0.0002)
    assert trace.usage(chapter_id="book:1")["attempts"] == 1
    assert "secret" not in json.dumps(trace.list(run_id="run"))
    http.close()


@pytest.mark.parametrize("provider_name", ["openai", "deepseek"])
def test_schema_retry_keeps_failed_attempt_usage(foundation, provider_name):
    _, trace, _ = foundation
    responses = iter(['{"wrong":1}', '{"summary":"recovered"}'])
    http = httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={
        "choices":[{"message":{"content":next(responses)}}], "usage":{"prompt_tokens":10,"completion_tokens":5}})))
    router = ModelRouter({"r":Route(provider=provider_name,model="m",max_retries=1)},
        {provider_name:ChatProvider(provider_name,"secret",client=http)}, trace, sleep=lambda _:None)
    assert router.generate("r",Prompt(version="1",template="JSON"),{},Output,context()).summary == "recovered"
    traces = trace.list(run_id="run")
    assert traces[0]["failure_class"] == "SchemaFailure"
    assert trace.usage(run_id="run")["input_tokens"] == 20
    assert trace.usage(run_id="run")["estimated_cost"] is None
    http.close()


@pytest.mark.parametrize("mode", ["missing", "provider", "timeout", "malformed"])
@pytest.mark.parametrize("provider_name", ["openai", "deepseek"])
def test_errors_are_classified_bounded_and_unknown_usage_not_zero(mode, foundation, provider_name):
    _, trace, _ = foundation
    calls = []
    def respond(req):
        calls.append(req)
        if mode == "timeout":
            raise httpx.ReadTimeout("secret",request=req)
        if mode == "malformed":
            return httpx.Response(200,json={"unexpected":"secret"})
        return httpx.Response(503,text="secret")
    http = httpx.Client(transport=httpx.MockTransport(respond))
    router = ModelRouter({"r":Route(provider=provider_name,model="m",max_retries=1)},
        {provider_name:ChatProvider(provider_name,"" if mode=="missing" else "secret",client=http)},trace,sleep=lambda _:None)
    with pytest.raises(ModelFailure):
        router.generate("r",Prompt(version="1",template="JSON"),{},Output,context())
    assert len(calls) <= 2
    usage = trace.usage(run_id="run")
    assert usage["input_tokens"] is None
    assert usage["unknown_usage_attempts"] >= 1
    assert "secret" not in json.dumps(trace.list(run_id="run"))
    http.close()


def test_artifacts_are_immutable_versioned_and_replay_safe(foundation):
    _, _, artifacts = foundation
    fields = dict(logical_id="analysis", version=1, artifact_type="OpportunityAnalysis", content={"summary":"one"},
                  context=context(), prompt=Prompt(version="1",template="JSON"), route="research", model="model", provider="deepseek")
    first = artifacts.save(**fields)
    assert artifacts.save(**fields) == first
    with pytest.raises(ValueError, match="immutable"):
        artifacts.save(**{**fields,"content":{"summary":"changed"}})
    second = artifacts.save(**{**fields,"version":2,"content":{"summary":"two"}})
    assert second["artifact_id"] != first["artifact_id"]
    assert artifacts.get(first["artifact_id"])["content"] == {"summary":"one"}
    assert first["source_refs"] == ["source@1"]


def test_tool_traces_are_not_model_usage(foundation):
    kernel, trace, _ = foundation
    kernel.telemetry = trace
    run = kernel.create("tool", "test", [{"step_key":"collect","handler":"noop","kind":"tool"}])
    kernel.tick()
    rows = trace.list(run_id=run["pipeline_run_id"])
    assert len(rows) == 1 and rows[0]["kind"] == "tool"
    assert rows[0]["status"] == "success"
    assert trace.usage(run_id=run["pipeline_run_id"])["attempts"] == 0


def test_semantic_replay_avoids_model_call_and_rejects_changed_input(foundation):
    from app.generation import SemanticRuntime
    _, trace, artifacts = foundation
    calls = []
    def respond(req):
        calls.append(req)
        return httpx.Response(200,json={"model":"resolved-model-version", "choices":[{"message":{"content":'{"summary":"result"}'}}]})
    http = httpx.Client(transport=httpx.MockTransport(respond))
    router = ModelRouter({"r":Route(provider="openai",model="configured-alias")},
                         {"openai":ChatProvider("openai","secret",client=http)},trace)
    runtime = SemanticRuntime(router,artifacts)
    kwargs = dict(route="r",prompt=Prompt(version="v1",template="JSON"), inputs={"summary":"source"},
        input_schema=Output,output_schema=Output,context=context(),logical_id="output",version=1,artifact_type="OpportunityAnalysis")
    first = runtime.execute(**kwargs)
    assert first["model"] == "resolved-model-version"
    assert runtime.execute(**kwargs) == first
    assert len(calls) == 1
    assert trace.list(run_id="run")[0]["output_refs"] == [first["artifact_id"]]
    with pytest.raises(ValueError,match="immutable"):
        runtime.execute(**{**kwargs,"inputs":{"summary":"different"}})
    assert len(calls) == 1
    http.close()


def test_trace_and_usage_apis_are_protected_and_serve_persisted_records(foundation):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.config import Settings
    kernel, trace, artifacts = foundation
    kernel.telemetry = trace
    kernel.artifacts = artifacts
    run = kernel.create("trace-api","test",[{"step_key":"x","handler":"noop","kind":"tool"}])
    kernel.tick()
    artifact = artifacts.save(logical_id="api-artifact",version=1,artifact_type="Test",content={"ok":True},
        context=context(),prompt=Prompt(version="1",template="JSON"),route="r",provider="openai",model="m")
    client = TestClient(create_app(Settings(BACKEND_API_KEY="test"),kernel=kernel))
    headers = {"x-api-key":"test"}
    for path in (f'/api/workflows/{run["pipeline_run_id"]}/trace',f'/api/workflows/{run["pipeline_run_id"]}/usage',
                 '/api/chapters/book:1/usage',f'/api/artifacts/{artifact["artifact_id"]}'):
        assert client.get(path).status_code == 401
        assert client.get(path,headers=headers).status_code == 200
    assert client.get('/api/artifacts/missing',headers=headers).status_code == 404
    kernel.telemetry = None
    assert client.get('/api/chapters/book:1/usage',headers=headers).status_code == 503
    client.close()


def test_generation_production_wiring_and_missing_route(foundation,monkeypatch,tmp_path):
    from app.runtime import build_runtime
    from app.config import Settings
    from app.feishu.client import FeishuClient
    kernel, _, _ = foundation
    for name in ("pipeline_runs","step_runs","approval_events","artifacts","traces"):
        monkeypatch.setenv("FEISHU_TABLE_ID_" + name.upper(), name)
    monkeypatch.setenv("FEISHU_APP_TOKEN","app")
    configured, client = build_runtime(Settings(BACKEND_API_KEY="test",FEISHU_APP_ID="fixture",
        FEISHU_APP_SECRET="fixture",HARNESS_JOURNAL_DIR=str(tmp_path/"wiring"),GENERATION_ENABLED=True,
        MODEL_ROUTES_JSON='{"research":{"provider":"deepseek","model":"configured-model"}}'))
    try:
        assert configured.model_router.routes["research"].provider == "deepseek"
        with pytest.raises(ModelFailure,match="MissingRoute"):
            configured.model_router.generate("missing",Prompt(version="1",template="JSON"),{},Output,context())
    finally:
        configured.model_router.close()
        client._http.close()


def test_rate_limit_and_non_retryable_provider_error(foundation):
    _, trace, _ = foundation
    calls = []
    codes = iter([429,401])
    http = httpx.Client(transport=httpx.MockTransport(lambda req:(calls.append(req) or httpx.Response(next(codes),text="secret"))))
    router = ModelRouter({"r":Route(provider="openai",model="m",max_retries=2)},
        {"openai":ChatProvider("openai","secret",client=http)},trace,sleep=lambda _:None)
    with pytest.raises(ModelFailure,match="ProviderFailure"):
        router.generate("r",Prompt(version="1",template="JSON"),{},Output,context())
    assert len(calls) == 2
    assert [r["failure_class"] for r in trace.list(run_id="run")] == ["RateLimited","ProviderFailure"]
    http.close()


def test_failed_tool_trace_has_sanitized_failure_class(foundation):
    kernel, trace, _ = foundation
    kernel.telemetry = trace
    def fail(step):
        raise RuntimeError("secret provider response")
    kernel.register("failure",fail)
    run = kernel.create("failed-tool","test",[{"step_key":"x","handler":"failure","kind":"tool"}])
    kernel.tick()
    rows = trace.list(run_id=run["pipeline_run_id"])
    assert rows[0]["failure_class"] == "RuntimeError"
    assert "secret" not in json.dumps(rows)


def test_truncated_output_is_not_accepted_and_retains_usage(foundation):
    _, trace, _ = foundation
    http = httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={
        "choices":[{"message":{"content":'{"summary":"partial"}'},"finish_reason":"length"}],
        "usage":{"prompt_tokens":10,"completion_tokens":100}})))
    router = ModelRouter({"r":Route(provider="openai",model="m",max_retries=0)},
        {"openai":ChatProvider("openai","secret",client=http)},trace)
    with pytest.raises(ModelFailure,match="TruncatedOutput"):
        router.generate("r",Prompt(version="1",template="JSON"),{},Output,context())
    assert trace.usage(run_id="run")["output_tokens"] == 100
    http.close()
