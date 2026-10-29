"""Saved public batches must reconcile safely or expose a blocked failure."""
from dataclasses import replace
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app.config import Settings
from app.harness import HarnessKernel
from app.main import create_app
from app.storage import AmbiguousWrite
from tests.test_hotspot_ingestion import ingestion as ingestion, complete


def hotspot_creates(transport):
    return [r for r in transport.calls
            if r.method == "POST" and r.url.path.endswith("/tables/hotspots/records")]


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/api/hotspots", None), ("GET", "/api/hotspots/missing", None),
    ("POST", "/api/hotspots/fetch", {"request_key": "unconfigured"})])
def test_disabled_hotspot_service_is_unavailable_not_an_empty_list(ingestion, method, path, body):
    _, _, storage, transport, _, root = ingestion
    kernel = HarnessKernel(storage, journal_dir=root / "unconfigured")
    api = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    offset = len(transport.calls)
    try:
        assert api.request(method, path, json=body).status_code == 401
        response = api.request(method, path, headers={"x-api-key": "test"}, json=body)
        assert response.status_code == 503
        assert response.json() == {"detail": "Hotspot ingestion is not configured"}
        assert transport.calls[offset:] == []
    finally:
        api.close()
        kernel.stop()


def test_blank_fetch_command_rejects_before_creating_run(ingestion):
    kernel, service, storage, _, _, _ = ingestion
    api = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    try:
        result = api.post("/api/hotspots/fetch", headers={"x-api-key": "test"},
                          json={"request_key": " \t "})
        assert result.status_code == 422
        assert result.json() == {"detail": "request_key must not be blank"}
        assert storage.list("pipeline_runs") == []
        service.collection_enabled = False
        with pytest.raises(ValueError, match="Hotspot collection is disabled"):
            service.enqueue("disabled")
        assert storage.list("pipeline_runs") == []
    finally:
        api.close()


def test_disabling_collection_blocks_already_queued_fetch_without_tool_call(ingestion):
    kernel, service, storage, transport, _, _ = ingestion
    run_id = service.enqueue("disabled-after-queue")["pipeline_run_id"]
    service.collection_enabled = False
    service.adapter = SimpleNamespace(fetch=lambda: pytest.fail("Disabled tool must not run"))
    run = complete(kernel, run_id)
    assert run["status"] == "blocked"
    assert run["steps"][0]["status"] == "blocked"
    traces = kernel.telemetry.list(run_id=run_id)
    assert traces[-1]["failure_class"] == "AmbiguousWrite"
    assert storage.list("hotspots") == [] and not hotspot_creates(transport)


def test_adapter_records_rejected_by_domain_schema_fail_without_persistence(ingestion):
    kernel, service, storage, transport, _, _ = ingestion
    valid = service.adapter.fetch().records[0]
    service.adapter = SimpleNamespace(fetch=lambda: SimpleNamespace(
        records=[replace(valid, title=" \t ")], raw_count=1, duration_ms=0))
    run = complete(kernel, service.enqueue("invalid-domain-records")["pipeline_run_id"])
    assert run["status"] == "failed"
    assert "OpenCLIOutputError" in run["steps"][0]["error_message"]
    assert kernel.telemetry.list(run_id=run["pipeline_run_id"])[-1]["failure_class"] == "OpenCLIOutputError"
    assert storage.list("hotspots") == [] and not hotspot_creates(transport)


@pytest.mark.parametrize("fetch_status", ["missing", "pending", "failed"])
def test_persistence_requires_successful_committed_fetch(ingestion, fetch_status):
    kernel, service, storage, transport, _, _ = ingestion
    run_id = service.enqueue("fetch-precondition")["pipeline_run_id"]
    run = kernel.get(run_id)
    fetched, persist = run["steps"]
    if fetch_status == "missing":
        storage.delete("step_runs", fetched["step_run_id"])
    elif fetch_status != "pending":
        storage.update("step_runs", fetched["step_run_id"], {"status": fetch_status})
    with pytest.raises(AmbiguousWrite, match="Persist requires a successful fetch snapshot"):
        service.persist(persist)
    assert storage.list("hotspots") == [] and not hotspot_creates(transport)


def test_changed_saved_batch_hash_blocks_without_replacing_snapshot_or_records(ingestion):
    kernel, service, storage, transport, _, _ = ingestion
    run_id = service.enqueue("tampered-batch")["pipeline_run_id"]
    kernel.tick()
    fetched = kernel.get(run_id)["steps"][0]
    snapshot = json.loads(fetched["output_json"])
    snapshot["records"][0]["rank"] += 1
    changed = json.dumps(snapshot)
    storage.update("step_runs", fetched["step_run_id"], {"output_json": changed})
    run = complete(kernel, run_id)
    assert run["status"] == "blocked" and run["steps"][1]["status"] == "blocked"
    assert kernel.telemetry.list(run_id=run_id)[-1]["failure_class"] == "AmbiguousWrite"
    assert storage.get("step_runs", fetched["step_run_id"])["output_json"] == changed
    assert storage.list("hotspots") == [] and not hotspot_creates(transport)


@pytest.mark.parametrize("field,value", [("source", "manual"), ("title", "Wrong identity"),
                                         ("url", "https://example.com/another-source")])
def test_existing_dedupe_identity_conflict_never_overwrites_record(ingestion, field, value):
    kernel, service, storage, transport, _, _ = ingestion
    record = service.adapter.fetch().records[0]
    fields = {"hotspot_id": "existing-source", "source": record.source,
              "title": record.title, "url": record.url, "dedupe_hash": record.dedupe_hash,
              "captured_at": "2026-09-27T00:00:00+00:00", "status": "discarded"}
    fields[field] = value
    original = storage.ensure("hotspots", fields)
    offset = len(hotspot_creates(transport))
    run = complete(kernel, service.enqueue("identity-conflict")["pipeline_run_id"])
    assert run["status"] == "blocked"
    assert kernel.telemetry.list(run_id=run["pipeline_run_id"])[-1]["failure_class"] == "AmbiguousWrite"
    assert storage.list("hotspots") == [original]
    assert len(hotspot_creates(transport)) == offset
    with pytest.raises(AmbiguousWrite, match="Hotspot identity does not match its dedupe key"):
        service.persist(run["steps"][1])
    assert storage.get("hotspots", "existing-source") == original


@pytest.mark.parametrize("capture", [None, "not-a-date", "2026-09-27T00:00:00", 42])
def test_invalid_stored_capture_blocks_ingestion_and_list_then_restores(ingestion, capture):
    kernel, service, storage, transport, _, _ = ingestion
    record = service.adapter.fetch().records[0]
    fields = {"hotspot_id": "bad-capture", "source": record.source, "title": record.title,
              "url": record.url, "dedupe_hash": record.dedupe_hash, "status": "discarded"}
    if capture is not None:
        fields["captured_at"] = capture
    original = storage.ensure("hotspots", fields)
    offset = len(hotspot_creates(transport))
    run = complete(kernel, service.enqueue("bad-stored-capture")["pipeline_run_id"])
    assert run["status"] == "blocked"
    assert len(hotspot_creates(transport)) == offset
    assert storage.list("hotspots") == [original]
    with pytest.raises(AmbiguousWrite, match="Invalid stored capture timestamp"):
        service.persist(run["steps"][1])
    api = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    try:
        response = api.get("/api/hotspots", headers={"x-api-key": "test"})
        assert response.status_code == 503
        assert response.json() == {"detail": "AmbiguousWrite", "reconciliation_required": True}
        assert storage.get("hotspots", "bad-capture") == original
        storage.update("hotspots", "bad-capture", {"captured_at": "2026-09-27T00:00:00+00:00"})
        restored = api.get("/api/hotspots", headers={"x-api-key": "test"})
        assert restored.status_code == 200 and restored.json()["total"] == 1
        assert restored.json()["items"][0]["status"] == "discarded"
    finally:
        api.close()
