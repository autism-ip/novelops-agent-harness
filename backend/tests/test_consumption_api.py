"""Authenticated downstream consumers enforce current approvals and immutable choices.

Real API/kernel/Feishu repositories with controlled HTTP and fixture model outputs;
this does not establish live-provider quality.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.test_creative_workflow import choose, creative as creative, enqueue as creative_enqueue, settle as creative_settle
from tests.test_research_workflow import enqueue as research_enqueue, research as research, settle as research_settle
HEADERS = {"x-api-key": "test"}


def observe_storage(kernel):
    requests = []
    kernel.storage._repos["hotspots"]._client._http.event_hooks["request"].append(requests.append)
    return requests


def assert_read_only(requests):
    assert requests
    assert all(request.method == "GET" or request.method == "POST"
        and request.url.path.endswith("/records/search") for request in requests)


def test_approved_analysis_http_consumption_needs_current_exact_approval(research):
    kernel, provider, _ = research
    run = research_enqueue(kernel)
    research_settle(kernel)
    run_id = run["pipeline_run_id"]
    path = f"/api/analyses/{run_id}/approved"
    requests = observe_storage(kernel)
    calls = len(provider.calls)
    # Endpoint contract only; scheduler lifespan has its own integration scope.
    api = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    try:
        assert api.get(path).status_code == 401 and not requests
        assert api.get("/api/analyses/missing/approved", headers=HEADERS).status_code == 404
        assert api.get(path, headers=HEADERS).status_code == 409
        state = kernel.research.get(run_id)
        gate = next(step for step in state["run"]["steps"] if step["step_key"] == "selection")
        body = {"step_id": gate["step_run_id"], "artifact_id": state["opportunity"]["artifact_id"],
            "expected_version": gate["output_version"], "operator": "editor", "action": "approve"}
        assert api.post(f"/api/analyses/{run_id}/decision", json=body, headers=HEADERS).status_code == 200
        research_settle(kernel)
        requests.clear()
        for _ in range(2):
            response = api.get(path, headers=HEADERS)
            assert response.status_code == 200 and response.json() == state["opportunity"]
        assert_read_only(requests)
        assert len(provider.calls) == calls
        kernel.storage.update("hotspots", "HS-test", {"status": "discarded"})
        requests.clear()
        assert api.get(path, headers=HEADERS).status_code == 409
        assert_read_only(requests)
        assert len(provider.calls) == calls
        assert len(kernel.storage.list("approval_events")) == 1

    finally:
        api.close()


@pytest.mark.parametrize("kind", ["titles", "covers"])
@pytest.mark.parametrize("change", ["discard_source", "tamper_artifact"])
def test_selected_creative_http_consumer_rechecks_source_and_hash(creative, kind, change):
    kernel, provider, source_run = creative
    if kind == "covers":
        titles = creative_enqueue(kernel, "titles", source_run)
        creative_settle(kernel)
        choose(kernel, titles["pipeline_run_id"])
        source_run = titles["pipeline_run_id"]
    run = creative_enqueue(kernel, kind, source_run)
    creative_settle(kernel)
    run_id = run["pipeline_run_id"]
    path = f"/api/creative/runs/{run_id}/selected"
    requests = observe_storage(kernel)
    calls = len(provider.calls)
    # Endpoint contract only; scheduler lifespan has its own integration scope.
    api = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    try:
        assert api.get(path).status_code == 401 and not requests
        assert api.get("/api/creative/runs/missing/selected", headers=HEADERS).status_code == 404
        assert api.get(path, headers=HEADERS).status_code == 409
        state = kernel.creative.read(run_id)
        gate = next(step for step in state["run"]["steps"] if step["step_key"] == "select")
        selected = state["candidates"][1]
        body = {"step_id": gate["step_run_id"], "artifact_id": selected["artifact_id"],
            "action": "approve", "expected_version": gate["output_version"], "operator": "editor"}
        assert api.post(f"/api/creative/runs/{run_id}/decision", json=body, headers=HEADERS).status_code == 200
        requests.clear()
        for _ in range(2):
            response = api.get(path, headers=HEADERS)
            assert response.status_code == 200 and response.json() == selected
        assert_read_only(requests)
        assert len(provider.calls) == calls
        if change == "discard_source":
            kernel.storage.update("hotspots", "HS-test", {"status": "discarded"})
            expected = 409
        else:
            row = kernel.storage.get("artifacts", selected["artifact_id"])
            payload = json.loads(row["payload_json"])
            payload["content"][next(iter(payload["content"]))] = "FORGED-CONTENT"
            kernel.storage.update("artifacts", selected["artifact_id"], {"payload_json": json.dumps(payload)})
            # Current public ArtifactIntegrityError contract maps to a safe 422.
            expected = 422
        requests.clear()
        response = api.get(path, headers=HEADERS)
        assert response.status_code == expected and "FORGED-CONTENT" not in response.text
        if change == "tamper_artifact":
            assert response.json() == {"detail": "Artifact integrity check failed"}
        assert_read_only(requests)
        assert len(provider.calls) == calls
    finally:
        api.close()
