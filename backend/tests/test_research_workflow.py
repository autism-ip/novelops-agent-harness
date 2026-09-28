"""Opportunity workflow acceptance through the real kernel and Feishu HTTP adapter."""
import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.generation import ArtifactStore, Completion, ModelFailure, ModelRouter, Route, SemanticRuntime, TraceRecorder
from app.harness import HarnessKernel, TransitionConflict
from app.main import create_app
from app.research import ResearchService
from tests.feishu_transport import make_storage


def opportunity(level="low", confidence=0.95):
    return {"summary": "A community solves a shared fictional problem.",
        "core_emotions": ["belonging"], "hit_patterns": ["cooperation under pressure"],
        "genre_fit": ["contemporary fantasy"], "reader_promise": "Earned trust and a satisfying solution",
        "novelization_directions": ["Use invented people in an imaginary town"],
        "risk": {"level": level, "flags": [], "reasons": ["Invented setting"],
                 "confidence": confidence, "uncertainties": []}}


class Provider:
    def __init__(self):
        self.outputs = []
        self.calls = []

    def complete(self, route, messages):
        self.calls.append((route.model, messages))
        result = self.outputs.pop(0) if self.outputs else opportunity()
        if isinstance(result, Exception):
            raise result
        return Completion(json.dumps(result), "fixture-resolved-model", 100, 50)


@pytest.fixture
def research(tmp_path):
    storage, transport, client = make_storage()
    kernel = HarnessKernel(storage, journal_dir=tmp_path, max_retries=3)
    provider = Provider()
    kernel.telemetry = TraceRecorder(kernel)
    kernel.artifacts = ArtifactStore(kernel)
    kernel.model_router = ModelRouter({k: Route(provider="openai", model=k, max_retries=1,
        input_cost_per_million=1, output_cost_per_million=2) for k in ("research", "risk")},
        {"openai": provider}, kernel.telemetry, sleep=lambda _: None)
    kernel.semantic = SemanticRuntime(kernel.model_router, kernel.artifacts)
    kernel.research = ResearchService(kernel, selection_required=True)
    storage.ensure("hotspots", {"hotspot_id": "HS-test", "source": "manual",
        "title": "Community gardens unite neighbors in an imaginary town", "url": "https://example.org/source",
        "category": "fiction", "captured_at": "2026-09-28T00:00:00+00:00", "status": "normalized"})
    yield kernel, provider, transport
    client._http.close()


def enqueue(kernel, **extra):
    ctx = kernel.research.context("HS-test")
    return kernel.research.enqueue({"hotspot_id": "HS-test", "version": ctx["next_version"],
        "source_hash": ctx["source_hash"], **extra})


def settle(kernel):
    for _ in range(8):
        kernel.tick()


def test_low_risk_skips_risk_gate_but_requires_configured_selection(research):
    kernel, provider, _ = research
    run = enqueue(kernel)
    settle(kernel)
    analysis = kernel.research.get(run["pipeline_run_id"])
    assert analysis["approval_status"] == "awaiting_selection"
    assert analysis["risk"]["content"]["requires_review"] is False
    assert analysis["opportunity"]["content"] == opportunity()
    gate = next(s for s in analysis["run"]["steps"] if s["step_key"] == "selection")
    body = {"action": "approve", "expected_version": gate["output_version"], "operator": "editor",
            "artifact_id": analysis["opportunity"]["artifact_id"], "step_id": gate["step_run_id"]}
    kernel.research.decide(run["pipeline_run_id"], **body)
    kernel.research.decide(run["pipeline_run_id"], **body)
    settle(kernel)
    assert kernel.research.approved(run["pipeline_run_id"])["artifact_id"] == body["artifact_id"]
    assert len(kernel.storage.list("approval_events")) == 1
    assert len(provider.calls) == 1
    assert len(kernel.storage.list("hotspot_analyses")) == 1
    assert kernel.telemetry.usage(run_id=run["pipeline_run_id"])["input_tokens"] == 100
    trace = next(t for t in kernel.telemetry.list(run_id=run["pipeline_run_id"]) if t["kind"] == "model")
    assert trace["input_refs"] and trace["output_refs"] and trace["latency_ms"] >= 0
    assert trace["model"] == "fixture-resolved-model"


@pytest.mark.parametrize("level,confidence", [("high", .99), ("low", .4), ("uncertain", .95)])
def test_risk_gate_cannot_be_downgraded_by_second_opinion(research, level, confidence):
    kernel, provider, _ = research
    provider.outputs = [opportunity(level, confidence), opportunity()["risk"]]
    run = enqueue(kernel)
    settle(kernel)
    result = kernel.research.get(run["pipeline_run_id"])
    assert result["approval_status"] == "awaiting_risk_review"
    assert len(provider.calls) == 2
    assert result["risk"]["content"]["requires_review"]


def test_schema_retry_and_permanent_failure_do_not_multiply_paid_calls(research):
    kernel, provider, _ = research
    provider.outputs = [{"invalid": True}, opportunity()]
    run = enqueue(kernel)
    settle(kernel)
    assert len(provider.calls) == 2
    assert kernel.research.get(run["pipeline_run_id"])["opportunity"]
    assert kernel.telemetry.list(run_id=run["pipeline_run_id"])[1]["failure_class"] == "SchemaFailure"
    provider.outputs = [ModelFailure("Timeout", True), ModelFailure("Timeout", True)]
    failed = enqueue(kernel)
    settle(kernel)
    assert len(provider.calls) == 4
    assert kernel.get(failed["pipeline_run_id"])["status"] == "failed"
    assert kernel.research.get(failed["pipeline_run_id"])["opportunity"] is None


def test_hotspot_remains_normalized_until_risk_artifact_is_validated(research):
    kernel, _, _ = research
    run = enqueue(kernel)
    kernel.tick()  # ResearchAgent produced a proposal, risk has not run yet.
    assert kernel.research.get(run["pipeline_run_id"])["opportunity"] is not None
    assert kernel.research.get(run["pipeline_run_id"])["risk"] is None
    assert kernel.storage.get("hotspots", "HS-test")["status"] == "normalized"
    kernel.tick()
    assert kernel.storage.get("hotspots", "HS-test")["status"] == "analyzed"


def test_versions_replay_and_stale_approval_protection(research):
    kernel, provider, _ = research
    context = kernel.research.context("HS-test")
    spec = {"hotspot_id": "HS-test", "version": 1, "source_hash": context["source_hash"]}
    first = kernel.research.enqueue(spec)
    settle(kernel)
    assert kernel.research.enqueue(spec)["pipeline_run_id"] == first["pipeline_run_id"]
    with pytest.raises(TransitionConflict):
        kernel.research.enqueue({**spec, "feedback": "Changed input"})
    old = kernel.research.get(first["pipeline_run_id"])
    second = enqueue(kernel)
    settle(kernel)
    assert kernel.research.get(second["pipeline_run_id"])["opportunity"]["version"] == 2
    step = next(s for s in old["run"]["steps"] if s["step_key"] == "selection")
    with pytest.raises(TransitionConflict):
        kernel.decide(step["step_run_id"], "approve", 1, "editor")
    assert len(provider.calls) == 2
    assert kernel.storage.list("approval_events") == []


def test_revise_records_exact_artifact_and_feedback_once(research):
    kernel, _, _ = research
    run = enqueue(kernel)
    settle(kernel)
    result = kernel.research.get(run["pipeline_run_id"])
    body = dict(action="revise", expected_version=1, operator="editor", reason="Invent a different setting",
        artifact_id=result["opportunity"]["artifact_id"],
        step_id=next(s["step_run_id"] for s in result["run"]["steps"] if s["step_key"] == "selection"))
    kernel.research.decide(run["pipeline_run_id"], **body)
    kernel.research.decide(run["pipeline_run_id"], **body)
    assert kernel.research.get(run["pipeline_run_id"])["approval_status"] == "revision_requested"
    revised = enqueue(kernel, revision_of=run["pipeline_run_id"], feedback=body["reason"])
    settle(kernel)
    assert kernel.research.get(revised["pipeline_run_id"])["opportunity"]["version"] == 2
    assert len(kernel.storage.list("approval_events")) == 1


def test_authenticated_trigger_and_product_read(research):
    kernel, _, _ = research
    client = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    headers = {"x-api-key": "test"}
    context = client.get("/api/hotspots/HS-test/research-context", headers=headers).json()
    body = {"request_key": "batch", "items": [{"hotspot_id": "HS-test", "version": 1, "source_hash": context["source_hash"]}]}
    assert client.post("/api/analyses", json=body).status_code == 401
    response = client.post("/api/analyses", json=body, headers=headers)
    assert response.status_code == 201
    settle(kernel)
    rid = response.json()["runs"][0]["pipeline_run_id"]
    result = client.get(f"/api/analyses/{rid}", headers=headers)
    assert result.status_code == 200 and result.json()["opportunity"]["content"] == opportunity()
    assert client.get("/api/hotspots/HS-test/analyses", headers=headers).json()[0]["run"]["pipeline_run_id"] == rid
    mismatch = {"action": "approve", "expected_version": 1, "operator": "editor", "artifact_id": "wrong", "step_id": "wrong"}
    assert client.post(f"/api/analyses/{rid}/decision", json=mismatch, headers=headers).status_code == 409
    client.close()


def test_schema_rules_reject_blank_semantic_content(research):
    kernel, provider, _ = research
    bad = copy.deepcopy(opportunity())
    bad["summary"] = "  "
    provider.outputs = [bad, bad]
    run = enqueue(kernel)
    settle(kernel)
    assert kernel.get(run["pipeline_run_id"])["status"] == "failed"
    assert kernel.storage.list("artifacts") == []


def test_risk_decision_retry_cannot_approve_next_selection_gate(research):
    kernel, provider, _ = research
    provider.outputs = [opportunity("high"), opportunity()["risk"]]
    run = enqueue(kernel)
    settle(kernel)
    analysis = kernel.research.get(run["pipeline_run_id"])
    gate = next(s for s in analysis["run"]["steps"] if s["step_key"] == "risk_gate")
    body = dict(action="approve", expected_version=1, operator="editor", step_id=gate["step_run_id"],
        artifact_id=analysis["opportunity"]["artifact_id"])
    kernel.research.decide(run["pipeline_run_id"], **body)
    settle(kernel)
    kernel.research.decide(run["pipeline_run_id"], **body)
    assert kernel.research.get(run["pipeline_run_id"])["approval_status"] == "awaiting_selection"
    assert len(kernel.storage.list("approval_events")) == 1


@pytest.mark.parametrize("change", ["discard", "source", "binding"])
def test_changed_source_and_tampered_binding_cannot_be_approved(research, change):
    kernel, _, _ = research
    run = enqueue(kernel)
    settle(kernel)
    result = kernel.research.get(run["pipeline_run_id"])
    step = next(s for s in result["run"]["steps"] if s["step_key"] == "selection")
    if change == "binding":
        kernel.storage.update("step_runs", step["step_run_id"], {"output_json": "{}"})
    else:
        kernel.storage.update("hotspots", "HS-test", {"status": "discarded"} if change == "discard" else {"title": "Changed source title"})
    with pytest.raises(TransitionConflict):
        kernel.decide(step["step_run_id"], "approve", 1, "editor")
    assert kernel.storage.list("approval_events") == []


def test_routine_automatic_policy_and_high_risk_override(research):
    kernel, provider, _ = research
    kernel.research.selection_required = False
    first = enqueue(kernel)
    settle(kernel)
    assert kernel.research.approved(first["pipeline_run_id"])["version"] == 1
    assert kernel.storage.list("approval_events") == []
    provider.outputs = [opportunity("high"), opportunity()["risk"]]
    second = enqueue(kernel)
    settle(kernel)
    assert kernel.research.get(second["pipeline_run_id"])["approval_status"] == "awaiting_risk_review"
    with pytest.raises(TransitionConflict):
        kernel.research.approved(first["pipeline_run_id"])


def test_deterministic_contact_flags_override_low_semantic_scores(research):
    kernel, provider, _ = research
    kernel.storage.update("hotspots", "HS-test", {"title": "A fictional incident; contact person@example.org for details", "url": ""})
    provider.outputs = [opportunity(), opportunity()["risk"]]
    run = enqueue(kernel)
    settle(kernel)
    result = kernel.research.get(run["pipeline_run_id"])
    assert set(result["risk"]["content"]["rule_flags"]) == {"missing_source_url", "possible_personal_contact"}
    assert result["approval_status"] == "awaiting_risk_review"
    assert result["risk"]["provider"] == "deterministic"


def test_projection_write_failure_restarts_without_repeating_model(research, monkeypatch):
    kernel, provider, _ = research
    run = enqueue(kernel)
    original = kernel.storage.update
    def offline(collection, key, data):
        if collection == "hotspot_analyses":
            raise RuntimeError("temporary projection failure")
        return original(collection, key, data)
    monkeypatch.setattr(kernel.storage, "update", offline)
    with pytest.raises(RuntimeError):
        kernel.tick()
    assert len(provider.calls) == 1
    assert next(s for s in kernel.get(run["pipeline_run_id"])["steps"] if s["step_key"] == "research")["status"] == "success"
    monkeypatch.setattr(kernel.storage, "update", original)
    kernel.recover()
    settle(kernel)
    assert len(provider.calls) == 1
    assert kernel.storage.list("hotspot_analyses")[0]["approval_status"] == "awaiting_selection"


def test_reserved_workflow_cannot_bypass_policy_through_generic_api(research):
    kernel, _, _ = research
    client = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    response = client.post("/api/workflows", headers={"x-api-key": "test"}, json={
        "request_key": "bypass", "workflow_type": "custom", "steps": [{"step_key": "a", "handler": "research.commit"}]})
    assert response.status_code == 422
    assert kernel.list() == []
    client.close()


def test_partial_batch_replays_completed_reservations_and_reports_conflicts(research):
    kernel, _, _ = research
    client = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    context = kernel.research.context("HS-test")
    item = {"hotspot_id": "HS-test", "version": 1, "source_hash": context["source_hash"]}
    body = {"request_key": "batch", "items": [item, {**item, "hotspot_id": "missing"}]}
    first = client.post("/api/analyses", json=body, headers={"x-api-key": "test"})
    replay = client.post("/api/analyses", json=body, headers={"x-api-key": "test"})
    assert first.status_code == replay.status_code == 201
    assert first.json()["runs"][0]["pipeline_run_id"] == replay.json()["runs"][0]["pipeline_run_id"]
    assert len(replay.json()["errors"]) == 1
    assert len(kernel.list()) == 1
    client.close()


def test_configuration_change_blocks_pending_research_without_model_call(research):
    kernel, provider, _ = research
    run = enqueue(kernel)
    kernel.research.selection_required = False
    settle(kernel)
    assert kernel.get(run["pipeline_run_id"])["status"] == "blocked"
    assert provider.calls == []


def test_research_production_wiring_requires_dependencies_and_both_routes(monkeypatch, tmp_path):
    from app.runtime import build_runtime
    with pytest.raises(ValueError, match="requires"):
        build_runtime(Settings(BACKEND_API_KEY="test", RESEARCH_ENABLED=True))
    for name in ("pipeline_runs", "step_runs", "approval_events", "hotspots", "artifacts", "traces", "hotspot_analyses"):
        monkeypatch.setenv("FEISHU_TABLE_ID_" + name.upper(), name)
    monkeypatch.setenv("FEISHU_APP_TOKEN", "app")
    options = dict(BACKEND_API_KEY="test", FEISHU_APP_ID="test", FEISHU_APP_SECRET="test",
        HARNESS_JOURNAL_DIR=str(tmp_path), RESEARCH_ENABLED=True, HOTSPOTS_ENABLED=True, GENERATION_ENABLED=True)
    with pytest.raises(ValueError, match="research model route"):
        build_runtime(Settings(**options))
    routes = {name: {"provider": "openai", "model": "configured"} for name in ("research", "risk")}
    kernel, client = build_runtime(Settings(**options, MODEL_ROUTES_JSON=json.dumps(routes)))
    try:
        assert kernel.research.selection_required
        assert "research.risk" in kernel.handlers
    finally:
        kernel.model_router.close()
        client._http.close()
