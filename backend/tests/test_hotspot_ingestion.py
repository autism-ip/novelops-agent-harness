"""Hotspot acceptance: actual subprocess, adapter, kernel, Feishu HTTP and API."""
import json
import sys
import time
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.generation import TraceRecorder
from app.harness import HarnessKernel
from app.hotspots import HotspotService
from app.main import create_app
from app.tools.adapters.douyin_hotspots import DouyinHotspotAdapter
from app.tools.runner import OpenCLIRunner
from tests.feishu_transport import make_storage


def batch(count=35):
    return [{"title": f"话题{i}", "rank": i+1, "hot_value": 100+i,
        "url": f"https://www.douyin.com/hot/{i}", "captured_at": "2026-09-28T00:00:00Z"}
        for i in range(count)]


@pytest.fixture
def ingestion(tmp_path):
    storage, transport, client = make_storage()
    kernel = HarnessKernel(storage, journal_dir=tmp_path/"journal", max_retries=1)
    kernel.telemetry = TraceRecorder(kernel)
    payload = tmp_path/"batch.json"
    payload.write_text(json.dumps(batch()), encoding="utf-8")
    script = tmp_path/"source.py"
    script.write_text("import sys\nprint(open(sys.argv[1], encoding='utf-8').read())\n")
    adapter = DouyinHotspotAdapter(OpenCLIRunner(sys.executable, 5), SimpleNamespace(OPENCLI_ENABLED=True),
                                  [str(script), str(payload)])
    service = HotspotService(kernel, adapter)
    kernel.hotspots = service
    yield kernel, service, storage, transport, payload, tmp_path
    kernel.stop()
    client._http.close()


def complete(kernel, run_id):
    for _ in range(6):
        kernel.tick()
    return kernel.get(run_id)


def test_fetch_35_through_subprocess_persistence_and_authenticated_api(ingestion):
    kernel, _, storage, _, _, _ = ingestion
    api = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    headers = {"x-api-key": "test"}
    assert api.post("/api/hotspots/fetch", json={"request_key": "one"}).status_code == 401
    response = api.post("/api/hotspots/fetch", headers=headers, json={"request_key": "one"})
    assert response.status_code == 201, response.text
    run = complete(kernel, response.json()["pipeline_run_id"])
    assert run["status"] == "completed"
    fetched, saved = [json.loads(s["output_json"]) for s in run["steps"]]
    assert fetched["counts"] == {"fetched": 35, "accepted": 35, "rejected": 0, "duplicate_in_batch": 0, "selected": 35, "omitted": 0}
    assert saved["created"] == 35 and saved["reconciled"] == 0
    assert len(storage.list("hotspots")) == 35
    listed = api.get("/api/hotspots?source=douyin&status=normalized&limit=10", headers=headers).json()
    assert listed["total"] == 35 and len(listed["items"]) == 10
    item = listed["items"][0]
    assert item["hotspot_id"].startswith("HS-") and len(item["dedupe_hash"]) == 64
    assert item["last_ingestion_run_id"] == run["pipeline_run_id"]
    detail = api.get(f'/api/hotspots/{item["hotspot_id"]}', headers=headers).json()
    assert detail["raw_json"]["title"] == detail["title"]
    assert api.get('/api/hotspots/missing', headers=headers).status_code == 404
    assert api.get('/api/hotspots', headers=headers).status_code == 200
    assert api.get('/api/hotspots').status_code == 401
    assert api.post('/api/hotspots/fetch', headers=headers, json={"request_key": "bad", "limit": 51}).status_code == 422
    assert api.post('/api/hotspots/fetch', headers=headers, json={"request_key": "bad", "command": ["publish"]}).status_code == 422
    assert {t["kind"] for t in kernel.telemetry.list(run_id=run["pipeline_run_id"])} == {"tool", "service"}
    assert kernel.telemetry.usage(run_id=run["pipeline_run_id"])["attempts"] == 0
    replay = api.post('/api/hotspots/fetch', headers=headers, json={"request_key": "one"})
    assert replay.json()["pipeline_run_id"] == run["pipeline_run_id"]
    assert len(storage.list("hotspots")) == 35
    api.close()


def test_reingestion_preserves_legacy_id_status_and_updates_only_newer_capture(ingestion):
    kernel, service, storage, _, payload, _ = ingestion
    record = service.adapter.fetch().records[0]
    storage.ensure("hotspots", {"hotspot_id": "legacy-uuid", "dedupe_hash": record.dedupe_hash,
        "source": record.source, "title": record.title, "url": record.url, "status": "discarded",
        "captured_at": "2026-09-27T00:00:00+00:00", "heat_value": 1})
    run = complete(kernel, service.enqueue("first")["pipeline_run_id"])
    assert run["status"] == "completed"
    existing = storage.get("hotspots", "legacy-uuid")
    assert existing["heat_value"] == 100 and existing["status"] == "discarded"
    payload.write_text(json.dumps([{**batch()[0], "hot_value": 999, "captured_at": "2026-09-26T00:00:00Z"}]))
    complete(kernel, service.enqueue("older")["pipeline_run_id"])
    assert storage.get("hotspots", "legacy-uuid") == existing
    assert len(storage.list("hotspots")) == 35


def test_snapshot_recovery_does_not_refetch_or_duplicate_partial_batch(ingestion, monkeypatch):
    kernel, service, storage, _, _, root = ingestion
    run_id = service.enqueue("restart")["pipeline_run_id"]
    kernel.tick()  # persist fetch output before any Hotspot writes
    original = storage.update
    failures = []
    def fail(collection, domain_id, fields):
        if collection == "step_runs" and fields.get("status") == "success" and not failures:
            failures.append(True)
            raise RuntimeError("completion lost")
        return original(collection, domain_id, fields)
    monkeypatch.setattr(storage, "update", fail)
    with pytest.raises(RuntimeError):
        kernel.tick()
    monkeypatch.setattr(storage, "update", original)
    restarted = HarnessKernel(storage, journal_dir=root/"journal", max_retries=2)
    restarted.telemetry = TraceRecorder(restarted)
    adapter = SimpleNamespace(fetch=lambda: pytest.fail("must reuse saved snapshot"))
    HotspotService(restarted, adapter)
    restarted.recover()
    assert complete(restarted, run_id)["status"] == "completed"
    assert len(storage.list("hotspots")) == 35


def test_committed_timeout_reconciles_without_second_hotspot_post(ingestion):
    kernel, service, storage, transport, _, _ = ingestion
    original = transport.__call__
    failed = []
    def timeout(request):
        response = original(request)
        if request.method == "POST" and "/tables/hotspots/" in str(request.url) and not failed:
            failed.append(True)
            raise httpx.ReadTimeout("response lost", request=request)
        return response
    repo_client = storage._repos["hotspots"]._client
    repo_client._http.close()
    repo_client._http = httpx.Client(transport=httpx.MockTransport(timeout))
    result = complete(kernel, service.enqueue("timeout")["pipeline_run_id"])
    assert result["status"] == "completed"
    assert len(storage.list("hotspots")) == 35
    assert sum(r.method == "POST" and "/tables/hotspots/" in str(r.url) for r in transport.calls) == 35


@pytest.mark.parametrize("payload", [[None, 3, {"title": {}}, {"title": " "}], {"error": "bad"}])
def test_schema_failures_are_visible_and_bounded(ingestion, payload):
    kernel, service, storage, _, path, _ = ingestion
    path.write_text(json.dumps(payload))
    run = complete(kernel, service.enqueue("bad")["pipeline_run_id"])
    assert run["status"] == "failed"
    assert "OpenCLIOutputError" in run["steps"][0]["error_message"]
    assert len(kernel.telemetry.list(run_id=run["pipeline_run_id"])) == 2
    assert storage.list("hotspots") == []


def test_mixed_batch_counts_duplicates_rejections_and_no_padding(ingestion):
    kernel, service, storage, _, path, _ = ingestion
    path.write_text(json.dumps(batch(3) + batch(1) + [None, {"title": ""}]))
    run = complete(kernel, service.enqueue("mixed")["pipeline_run_id"])
    result = json.loads(run["steps"][1]["output_json"])
    assert result["counts"] == {"fetched": 6, "accepted": 4, "rejected": 2, "duplicate_in_batch": 1, "selected": 3, "omitted": 0}
    assert len(storage.list("hotspots")) == 3


@pytest.mark.parametrize("error_name", ["OpenCLITimeoutError", "OpenCLIExitError", "OpenCLIOutputError"])
def test_typed_tool_failure_is_sanitized_in_step_and_trace(ingestion, error_name):
    from app.tools.errors import OpenCLITimeoutError, OpenCLIExitError, OpenCLIOutputError
    kernel, service, _, _, _, _ = ingestion
    errors = {"OpenCLITimeoutError": OpenCLITimeoutError(5), "OpenCLIExitError": OpenCLIExitError(2, "secret"),
              "OpenCLIOutputError": OpenCLIOutputError("secret")}
    def fail():
        raise errors[error_name]
    service.adapter = SimpleNamespace(fetch=fail)
    run = complete(kernel, service.enqueue(error_name)["pipeline_run_id"])
    traces = kernel.telemetry.list(run_id=run["pipeline_run_id"])
    assert run["status"] == "failed" and len(traces) == 2
    assert traces[-1]["failure_class"] == error_name
    assert "secret" not in json.dumps(run) + json.dumps(traces)


def test_empty_feed_is_successful_and_has_no_fabricated_records(ingestion):
    kernel, service, storage, _, path, _ = ingestion
    path.write_text("[]")
    run = complete(kernel, service.enqueue("empty")["pipeline_run_id"])
    assert run["status"] == "completed"
    assert json.loads(run["steps"][1]["output_json"])["counts"]["fetched"] == 0
    assert storage.list("hotspots") == []


def test_generation_disabled_production_composition_still_traces_ingestion(monkeypatch, tmp_path):
    from app.runtime import build_runtime
    monkeypatch.setenv("FEISHU_APP_TOKEN", "fixture")
    for name in ("pipeline_runs", "step_runs", "approval_events", "hotspots", "traces"):
        monkeypatch.setenv("FEISHU_TABLE_ID_" + name.upper(), name)
    settings = Settings(BACKEND_API_KEY="test", FEISHU_APP_ID="test", FEISHU_APP_SECRET="test", OPENCLI_ENABLED=True,
        OPENCLI_DOUYIN_COMMAND=["configured", "public-feed"], HARNESS_JOURNAL_DIR=str(tmp_path))
    kernel, client = build_runtime(settings)
    try:
        assert kernel.hotspots and kernel.telemetry
        assert not getattr(kernel, "model_router", None)
        assert kernel.hotspots.adapter._cmd == ["configured", "public-feed"]
    finally:
        client._http.close()


def test_feed_limit_and_date_filters_are_explicit(ingestion):
    kernel, service, _, _, path, _ = ingestion
    path.write_text(json.dumps(batch(55)))
    run = complete(kernel, service.enqueue("limit", 30)["pipeline_run_id"])
    output = json.loads(run["steps"][1]["output_json"])
    assert output["counts"]["selected"] == 30 and output["counts"]["omitted"] == 25
    api = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    headers = {"x-api-key": "test"}
    assert len(api.get('/api/hotspots?offset=25&limit=10', headers=headers).json()["items"]) == 5
    assert api.get('/api/hotspots?captured_from=2026-09-29T00:00:00Z', headers=headers).json()["total"] == 0
    assert api.get('/api/hotspots?captured_to=2026-09-27T00:00:00Z', headers=headers).json()["total"] == 0
    assert api.get('/api/hotspots?captured_to=2026-09-27T00:00:00', headers=headers).status_code == 422
    assert api.get('/api/hotspots?captured_from=2026-09-29T00:00:00Z&captured_to=2026-09-27T00:00:00Z', headers=headers).status_code == 422
    api.close()


def test_unknown_hotspot_create_stops_and_restart_never_reposts(ingestion):
    kernel, service, storage, transport, _, root = ingestion
    original = transport.__call__
    attempts = []
    def timeout(request):
        if request.method == "POST" and "/tables/hotspots/" in str(request.url):
            attempts.append(request)
            raise httpx.ReadTimeout("unknown", request=request)
        return original(request)
    client = storage._repos["hotspots"]._client
    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(timeout))
    run = complete(kernel, service.enqueue("unknown")["pipeline_run_id"])
    assert run["status"] == "blocked" and len(attempts) == 1
    restarted = HarnessKernel(storage, journal_dir=root/"journal")
    restarted.telemetry = TraceRecorder(restarted)
    second = HotspotService(restarted, service.adapter)
    restarted.recover()
    assert complete(restarted, second.enqueue("second-request")["pipeline_run_id"])["status"] == "blocked"
    assert len(attempts) == 1


def test_partial_storage_failure_is_observable_and_does_not_recreate(ingestion):
    kernel, service, storage, transport, _, _ = ingestion
    transport.fail_create = "hotspots"
    run = complete(kernel, service.enqueue("storage-fail")["pipeline_run_id"])
    assert run["status"] == "blocked"
    assert storage.list("hotspots") == []
    assert [t["failure_class"] for t in kernel.telemetry.list(run_id=run["pipeline_run_id"])] == [None, "FeishuAPIError", "AmbiguousWrite"]


def test_corrupt_snapshot_and_duplicate_dedupe_keys_block(ingestion):
    kernel, service, storage, _, _, _ = ingestion
    run_id = service.enqueue("corrupt")["pipeline_run_id"]
    kernel.tick()
    fetched = kernel.get(run_id)["steps"][0]
    storage.update("step_runs", fetched["step_run_id"], {"output_json": "{}"})
    assert complete(kernel, run_id)["status"] == "blocked"
    assert storage.list("hotspots") == []
    record = service.adapter.fetch().records[0]
    for index in range(2):
        storage.ensure("hotspots", {"hotspot_id": str(index), "dedupe_hash": record.dedupe_hash})
    assert complete(kernel, service.enqueue("duplicate")["pipeline_run_id"])["status"] == "blocked"
    assert len(storage.list("hotspots")) == 2


def test_command_configuration_changes_block_old_unexecuted_work(ingestion):
    kernel, service, _, _, _, _ = ingestion
    run_id = service.enqueue("command")["pipeline_run_id"]
    service.command_hash = "changed"
    assert complete(kernel, run_id)["status"] == "blocked"


def test_hotspot_reads_survive_disabling_collection(ingestion):
    kernel, service, _, _, _, _ = ingestion
    complete(kernel, service.enqueue("read-only")["pipeline_run_id"])
    service.collection_enabled = False
    api = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    headers = {"x-api-key": "test"}
    assert api.get('/api/hotspots', headers=headers).json()["total"] == 35
    assert api.post('/api/hotspots/fetch', headers=headers, json={"request_key": "disabled"}).status_code == 503
    api.close()


def test_production_lifespan_schedules_ingestion_without_model_configuration(ingestion, monkeypatch):
    from app import runtime as composition
    kernel, service, storage, _, _, root = ingestion
    http_client = storage._repos["hotspots"]._client
    monkeypatch.setattr(composition, "FeishuClient", lambda *_: http_client)
    monkeypatch.setenv("FEISHU_APP_TOKEN", "fixture")
    for name in ("pipeline_runs", "step_runs", "approval_events", "hotspots", "traces"):
        monkeypatch.setenv("FEISHU_TABLE_ID_" + name.upper(), name)
    settings = Settings(BACKEND_API_KEY="test", HARNESS_ENABLED=True, OPENCLI_ENABLED=True,
        opencli_bin=sys.executable, OPENCLI_DOUYIN_COMMAND=service.adapter._cmd,
        HARNESS_POLL_INTERVAL=0.01, HARNESS_JOURNAL_DIR=str(root/"production"))
    with TestClient(create_app(settings)) as api:
        headers = {"x-api-key": "test"}
        response = api.post('/api/hotspots/fetch', headers=headers, json={"request_key": "scheduled"})
        assert response.status_code == 201
        run_id = response.json()["pipeline_run_id"]
        deadline = time.monotonic()+3
        while time.monotonic() < deadline:
            result = api.get(f'/api/workflows/{run_id}', headers=headers).json()
            if result["status"] == "completed":
                break
            time.sleep(0.01)
        assert result["status"] == "completed"
        assert api.get('/api/hotspots', headers=headers).json()["total"] == 35
        traces = api.get(f'/api/workflows/{run_id}/trace', headers=headers).json()
        assert len(traces) == 2 and all(t["status"] == "success" for t in traces)
        assert not hasattr(api.app.state.kernel, "model_router")
    assert not api.app.state.kernel.running


def test_read_only_configuration_and_missing_command_fail_fast(monkeypatch, tmp_path):
    from app.runtime import build_runtime
    monkeypatch.setenv("FEISHU_APP_TOKEN", "fixture")
    for name in ("pipeline_runs", "step_runs", "approval_events", "hotspots"):
        monkeypatch.setenv("FEISHU_TABLE_ID_" + name.upper(), name)
    common = dict(BACKEND_API_KEY="test", FEISHU_APP_ID="test", FEISHU_APP_SECRET="test", HARNESS_JOURNAL_DIR=str(tmp_path))
    with pytest.raises(ValueError, match="OPENCLI_DOUYIN_COMMAND"):
        build_runtime(Settings(**common, OPENCLI_ENABLED=True))
    kernel, client = build_runtime(Settings(**common, HOTSPOTS_ENABLED=True))
    try:
        assert not kernel.hotspots.collection_enabled
        assert "hotspots.fetch" not in kernel.handlers
        assert not kernel.telemetry
    finally:
        client._http.close()


def test_invalid_urls_and_timestamps_are_rejected_without_poisoning_valid_records(ingestion):
    kernel, service, storage, _, path, _ = ingestion
    path.write_text(json.dumps(batch(1) + [
        {"title": "x", "url": "javascript:alert(1)"},
        {"title": "x", "url": {"private": "bad"}},
        {"title": "x", "captured_at": "2026-09-28T00:00:00"},
        {"title": "x", "captured_at": "invalid"}]))
    result = complete(kernel, service.enqueue("invalid-fields")["pipeline_run_id"])
    assert result["status"] == "completed"
    counts = json.loads(result["steps"][1]["output_json"])["counts"]
    assert counts["rejected"] == 4 and counts["selected"] == 1
    assert len(storage.list("hotspots")) == 1
