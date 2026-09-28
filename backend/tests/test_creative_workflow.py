"""ZEN-36: exact approved source, ten titles, three covers, choices and failure paths."""
import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.creative import CreativeService
from app.generation import ArtifactStore, Completion, ModelFailure, ModelRouter, Route, SemanticRuntime, TraceRecorder
from app.harness import HarnessKernel, TransitionConflict
from app.main import create_app
from app.research import ResearchService
from tests.feishu_transport import make_storage
from tests.test_research_workflow import opportunity


def titles():
    return {"candidates": [{"title": f"The Garden of Star {i}", "hook": "A forgotten town remembers",
        "selling_point": "Cooperative fantasy", "click_score": 80, "genre_fit_score": 90,
        "risk_notes": "Fictional setting"} for i in range(10)]}


def covers():
    return {"directions": [{"visual_direction": f"Magical garden angle {i}",
        "main_elements": ["invented town", "glowing flowers"], "style": "painted fantasy",
        "cover_prompt": f"Paint original magical garden angle {i} with no real persons",
        "negative_prompt": "logos, real likenesses"} for i in range(3)]}


class Provider:
    def __init__(self):
        self.outputs = []
        self.calls = []
        self.messages = []

    def complete(self, route, messages):
        self.calls.append(route.model)
        self.messages.append(messages)
        value = self.outputs.pop(0) if self.outputs else (titles() if route.model == "titles" else
            covers() if route.model == "covers" else opportunity())
        if isinstance(value, Exception):
            raise value
        return Completion(json.dumps(value), route.model + "-resolved", 100, 50)


@pytest.fixture
def creative(tmp_path):
    storage, _, client = make_storage()
    kernel = HarnessKernel(storage, journal_dir=tmp_path, max_retries=3)
    provider = Provider()
    kernel.telemetry = TraceRecorder(kernel)
    kernel.artifacts = ArtifactStore(kernel)
    kernel.model_router = ModelRouter({k: Route(provider="openai", model=k, max_retries=1)
        for k in ("research", "risk", "titles", "covers")}, {"openai": provider}, kernel.telemetry, sleep=lambda _: None)
    kernel.semantic = SemanticRuntime(kernel.model_router, kernel.artifacts)
    kernel.research = ResearchService(kernel)
    kernel.creative = CreativeService(kernel)
    storage.ensure("hotspots", {"hotspot_id": "HS-test", "source": "manual",
        "title": "A fictional garden unites the town", "url": "https://example.org/story",
        "category": "fiction", "captured_at": "2026-09-28T00:00:00+00:00", "status": "normalized"})
    context = kernel.research.context("HS-test")
    research = kernel.research.enqueue({"hotspot_id": "HS-test", "version": 1, "source_hash": context["source_hash"]})
    for _ in range(5):
        kernel.tick()
    state = kernel.research.get(research["pipeline_run_id"])
    gate = next(s for s in state["run"]["steps"] if s["step_key"] == "selection")
    kernel.research.decide(research["pipeline_run_id"], action="approve", expected_version=1,
        operator="editor", artifact_id=state["opportunity"]["artifact_id"], step_id=gate["step_run_id"])
    for _ in range(3):
        kernel.tick()
    yield kernel, provider, research["pipeline_run_id"]
    client._http.close()


def enqueue(kernel, kind, source_run_id, version=None):
    context = kernel.creative.context(kind, source_run_id)
    return kernel.creative.enqueue(kind, {"source_run_id": source_run_id,
        "source_artifact_id": context["source_artifact_id"], "version": version or context["next_version"]})


def settle(kernel):
    for _ in range(8):
        kernel.tick()


def choose(kernel, run_id, index=0):
    state = kernel.creative.read(run_id)
    gate = next(s for s in state["run"]["steps"] if s["step_key"] == "select")
    body = {"step_id": gate["step_run_id"], "artifact_id": state["candidates"][index]["artifact_id"],
            "action": "approve", "expected_version": gate["output_version"], "operator": "editor"}
    kernel.creative.decide(run_id, **body)
    return body


def test_title_and_cover_require_exact_selection_and_project_versions(creative):
    kernel, provider, source_run = creative
    title_run = enqueue(kernel, "titles", source_run)
    settle(kernel)
    state = kernel.creative.read(title_run["pipeline_run_id"])
    assert state["run"]["status"] == "awaiting_approval"
    assert len(state["candidates"]) == 10
    assert len({item["content"]["title"] for item in state["candidates"]}) == 10
    assert len(kernel.storage.list("title_candidates")) == 10
    assert all(item["source_refs"] for item in state["candidates"])
    assert all(item["content_hash"] for item in state["candidates"])
    assert kernel.telemetry.usage(run_id=title_run["pipeline_run_id"])["input_tokens"] == 100
    with pytest.raises(TransitionConflict):
        kernel.creative.selected("titles", title_run["pipeline_run_id"])
    selected = choose(kernel, title_run["pipeline_run_id"], 3)
    kernel.creative.decide(title_run["pipeline_run_id"], **selected)
    assert kernel.creative.selected("titles", title_run["pipeline_run_id"])["artifact_id"] == selected["artifact_id"]
    assert len(kernel.storage.list("approval_events")) == 2  # Source opportunity + title.
    assert sum(row["approval_status"] == "approved" for row in kernel.storage.list("title_candidates")) == 1
    cover_run = enqueue(kernel, "covers", title_run["pipeline_run_id"])
    settle(kernel)
    covers_state = kernel.creative.read(cover_run["pipeline_run_id"])
    assert len(covers_state["candidates"]) == 3
    assert len(kernel.storage.list("cover_plans")) == 3
    assert all(item["source_refs"] for item in covers_state["candidates"])
    selected_cover = choose(kernel, cover_run["pipeline_run_id"], 2)
    assert kernel.creative.selected("covers", cover_run["pipeline_run_id"])["artifact_id"] == selected_cover["artifact_id"]
    assert kernel.storage.list("cover_plans")[2]["approval_status"] == "approved"
    assert provider.calls == ["research", "titles", "covers"]


@pytest.mark.parametrize("invalid", ["duplicate", "too_few", "risky"])
def test_bad_titles_are_retried_before_any_artifact_is_saved(creative, invalid):
    kernel, provider, source_run = creative
    bad = copy.deepcopy(titles())
    if invalid == "duplicate":
        bad["candidates"][1]["title"] = " the GARDEN of STAR 0!! "
    elif invalid == "too_few":
        bad["candidates"] = bad["candidates"][:9]
    else:
        bad["candidates"][0]["title"] = "Contact person@example.org"
    provider.outputs = [bad, bad]
    run = enqueue(kernel, "titles", source_run)
    settle(kernel)
    assert kernel.creative.read(run["pipeline_run_id"])["run"]["status"] == "failed"
    assert kernel.creative.read(run["pipeline_run_id"])["batch"] is None
    assert kernel.storage.list("title_candidates") == []
    assert provider.calls == ["research", "titles", "titles"]


def test_duplicate_cover_directions_are_rejected_before_review(creative):
    kernel, provider, source_run = creative
    title_run = enqueue(kernel, "titles", source_run)
    settle(kernel)
    choose(kernel, title_run["pipeline_run_id"])
    bad = covers()
    bad["directions"][1] = copy.deepcopy(bad["directions"][0])
    provider.outputs = [bad, bad]
    run = enqueue(kernel, "covers", title_run["pipeline_run_id"])
    settle(kernel)
    assert kernel.get(run["pipeline_run_id"])["status"] == "failed"
    assert kernel.storage.list("cover_plans") == []


def test_versions_preserve_prior_choices_but_only_latest_can_be_consumed(creative):
    kernel, provider, source_run = creative
    first = enqueue(kernel, "titles", source_run)
    settle(kernel)
    chosen = choose(kernel, first["pipeline_run_id"])
    second = enqueue(kernel, "titles", source_run)
    settle(kernel)
    assert kernel.creative.read(second["pipeline_run_id"])["candidates"][0]["version"] == 2
    assert kernel.creative.read(first["pipeline_run_id"])["candidates"][0]["version"] == 1
    with pytest.raises(TransitionConflict):
        kernel.creative.selected("titles", first["pipeline_run_id"])
    with pytest.raises(TransitionConflict):
        kernel.creative.decide(first["pipeline_run_id"], **{**chosen, "artifact_id": "AR-fake"})
    assert len(provider.calls) == 3


def test_approved_source_is_required_for_title_context_and_api(creative):
    kernel, _, source_run = creative
    client = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    headers = {"x-api-key": "test"}
    assert client.get(f"/api/creative/titles/{source_run}/context").status_code == 401
    context = client.get(f"/api/creative/titles/{source_run}/context", headers=headers).json()
    body = {"source_run_id": source_run, "source_artifact_id": context["source_artifact_id"], "version": 1}
    response = client.post("/api/creative/titles", json=body, headers=headers)
    assert response.status_code == 201
    assert client.post("/api/creative/titles", json=body, headers=headers).json() == response.json()
    settle(kernel)
    run_id = response.json()["pipeline_run_id"]
    assert len(client.get(f"/api/creative/runs/{run_id}", headers=headers).json()["candidates"]) == 10
    assert len(client.get(f"/api/creative/titles/{source_run}/runs", headers=headers).json()) == 1
    client.close()


def test_provider_failure_does_not_repeat_paid_calls_in_kernel(creative):
    kernel, provider, source_run = creative
    provider.outputs = [ModelFailure("Timeout", True), ModelFailure("Timeout", True)]
    run = enqueue(kernel, "titles", source_run)
    settle(kernel)
    assert provider.calls == ["research", "titles", "titles"]
    assert kernel.get(run["pipeline_run_id"])["status"] == "failed"
    assert kernel.telemetry.usage(run_id=run["pipeline_run_id"])["attempts"] == 2


def test_revision_feedback_uses_exact_prior_candidates_and_keeps_old_version(creative):
    kernel, provider, source_run = creative
    first = enqueue(kernel, "titles", source_run)
    settle(kernel)
    state = kernel.creative.read(first["pipeline_run_id"])
    gate = next(s for s in state["run"]["steps"] if s["step_key"] == "select")
    decision = dict(step_id=gate["step_run_id"], artifact_id="", expected_version=gate["output_version"],
                    action="revise", operator="editor", reason="Use a hopeful tone")
    kernel.creative.decide(first["pipeline_run_id"], **decision)
    kernel.creative.decide(first["pipeline_run_id"], **decision)
    context = kernel.creative.context("titles", source_run)
    with pytest.raises(TransitionConflict):
        kernel.creative.enqueue("titles", {"source_run_id": source_run,
            "source_artifact_id": context["source_artifact_id"], "version": 2,
            "revision_of": first["pipeline_run_id"]})
    second = kernel.creative.enqueue("titles", {"source_run_id": source_run,
        "source_artifact_id": context["source_artifact_id"], "version": 2,
        "revision_of": first["pipeline_run_id"], "feedback": "Use a hopeful tone"})
    settle(kernel)
    assert kernel.creative.read(second["pipeline_run_id"])["run"]["status"] == "awaiting_approval"
    generation_input = json.loads(provider.messages[-1][-1]["content"])
    assert generation_input["feedback"] == "Use a hopeful tone"
    assert len(generation_input["previous_candidates"]) == 10
    assert len(kernel.creative.read(first["pipeline_run_id"])["candidates"]) == 10
    assert len(kernel.storage.list("approval_events")) == 2


def test_generic_decision_cannot_choose_without_explicit_candidate(creative):
    kernel, _, source_run = creative
    title = enqueue(kernel, "titles", source_run)
    settle(kernel)
    state = kernel.creative.read(title["pipeline_run_id"])
    gate = next(s for s in state["run"]["steps"] if s["step_key"] == "select")
    with pytest.raises(TransitionConflict):
        kernel.decide(gate["step_run_id"], "approve", 1, "editor")
    assert len(kernel.storage.list("approval_events")) == 1


def test_creative_version_namespace_cannot_be_preempted(creative):
    kernel, _, source_run = creative
    context = kernel.creative.context("titles", source_run)
    key = kernel.creative.identity("titles", source_run, 1)
    client = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    response = client.post("/api/workflows", headers={"x-api-key": "test"}, json={
        "request_key": key, "workflow_type": "foreign", "steps": [{"step_key": "a", "handler": "noop"}]})
    assert response.status_code == 422
    kernel.create(key, "foreign", [{"step_key": "a", "handler": "noop"}])
    with pytest.raises(TransitionConflict, match="occupied"):
        kernel.creative.enqueue("titles", {"source_run_id": source_run,
            "source_artifact_id": context["source_artifact_id"], "version": 1})
    client.close()


def test_creative_revision_cannot_use_superseded_parent(creative):
    kernel, _, source_run = creative
    first = enqueue(kernel, "titles", source_run)
    settle(kernel)
    state = kernel.creative.read(first["pipeline_run_id"])
    gate = next(s for s in state["run"]["steps"] if s["step_key"] == "select")
    kernel.creative.decide(first["pipeline_run_id"], step_id=gate["step_run_id"], artifact_id="",
        expected_version=1, action="revise", operator="editor", reason="Change hook")
    second = kernel.creative.enqueue("titles", {"source_run_id": source_run,
        "source_artifact_id": state["request"]["source_artifact_id"], "version": 2,
        "revision_of": first["pipeline_run_id"], "feedback": "Change hook"})
    settle(kernel)
    context = kernel.creative.context("titles", source_run)
    with pytest.raises(TransitionConflict):
        kernel.creative.enqueue("titles", {"source_run_id": source_run,
            "source_artifact_id": context["source_artifact_id"], "version": 3,
            "revision_of": first["pipeline_run_id"], "feedback": "Stale feedback"})
    assert kernel.creative.read(second["pipeline_run_id"])["current"]


def test_creative_production_wiring_requires_research_routes_and_tables(monkeypatch, tmp_path):
    from app.runtime import build_runtime

    with pytest.raises(ValueError, match="CREATIVE_ENABLED requires RESEARCH_ENABLED"):
        build_runtime(Settings(BACKEND_API_KEY="test", CREATIVE_ENABLED=True))
    for name in ("pipeline_runs", "step_runs", "approval_events", "hotspots", "artifacts",
                 "traces", "hotspot_analyses", "title_candidates", "cover_plans"):
        monkeypatch.setenv("FEISHU_TABLE_ID_" + name.upper(), name)
    monkeypatch.setenv("FEISHU_APP_TOKEN", "app")
    options = dict(BACKEND_API_KEY="test", FEISHU_APP_ID="test", FEISHU_APP_SECRET="test",
        HARNESS_JOURNAL_DIR=str(tmp_path), HOTSPOTS_ENABLED=True, GENERATION_ENABLED=True,
        RESEARCH_ENABLED=True, CREATIVE_ENABLED=True)
    routes = {name: {"provider": "openai", "model": "configured"}
              for name in ("research", "risk", "titles", "covers")}
    with pytest.raises(ValueError, match="titles model route"):
        build_runtime(Settings(**options, MODEL_ROUTES_JSON=json.dumps({k: v for k, v in routes.items() if k != "titles"})))
    kernel, client = build_runtime(Settings(**options, MODEL_ROUTES_JSON=json.dumps(routes)))
    try:
        assert kernel.creative is not None
        assert all(name in kernel.storage._repos for name in ("title_candidates", "cover_plans"))
        response = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel)).get(
            "/api/hotspots/capabilities", headers={"x-api-key": "test"})
        assert response.json()["creative"] is True
    finally:
        kernel.model_router.close()
        client._http.close()
