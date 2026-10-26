"""Source numeric aliases survive the real local tool and durable HTTP boundary."""
import json

from fastapi.testclient import TestClient
import pytest

from app.config import Settings
from app.main import create_app
from tests.test_hotspot_ingestion import ingestion as ingestion, complete


@pytest.mark.parametrize("rank,heat,expected", [
    ("7", "12345", (7, 12345)),
    ("not-a-rank", "not-a-heat", (0, 0)),
    ("7.5", "12.5", (0, 0)),
    (7.5, [12345], (0, 0)),
    ({"value": 7}, 12.5, (0, 0)),
])
def test_numeric_aliases_normalize_without_losing_original_source(ingestion, rank, heat, expected):
    kernel, service, storage, transport, payload, _ = ingestion
    source = {"title": "Synthetic numeric source", "position": rank, "hotValue": heat,
              "url": "https://example.com/numeric-source", "captured_at": "2026-10-27T00:00:00Z"}
    payload.write_text(json.dumps([source]), encoding="utf-8")
    run = complete(kernel, service.enqueue("numeric-source")["pipeline_run_id"])
    assert run["status"] == "completed"
    fetched, saved = [json.loads(step["output_json"]) for step in run["steps"]]
    assert fetched["counts"] == {"fetched": 1, "accepted": 1, "rejected": 0,
                                 "duplicate_in_batch": 0, "selected": 1, "omitted": 0}
    assert saved["created"] == 1
    rows = storage.list("hotspots")
    assert len(rows) == 1
    assert (rows[0]["rank"], rows[0]["heat_value"]) == expected
    assert json.loads(rows[0]["raw_json"]) == source
    posts = [r for r in transport.calls if r.method == "POST" and r.url.path.endswith("/tables/hotspots/records")]
    assert len(posts) == 1
    api = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    try:
        response = api.get("/api/hotspots", headers={"x-api-key": "test"})
        assert response.status_code == 200
        row = response.json()["items"][0]
        assert (row["rank"], row["heat_value"]) == expected and row["raw_json"] == source
        assert row["status"] == "normalized" and row["hotspot_id"] == rows[0]["hotspot_id"]
        assert kernel.telemetry.usage(run_id=run["pipeline_run_id"])["attempts"] == 0
    finally:
        api.close()
