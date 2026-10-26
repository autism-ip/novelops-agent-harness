"""Externally conflicting manual identities stop without overwriting business rows."""
from copy import deepcopy

import pytest

from tests.test_hotspot_ingestion import ingestion as ingestion, complete


def writes(transport, offset):
    return [r for r in transport.calls[offset:] if "/tables/hotspots/records" in r.url.path and
            (r.method in {"PUT", "DELETE"} or r.method == "POST" and not r.url.path.endswith("/search"))]


@pytest.mark.parametrize("field,value", [
    ("source", "douyin"), ("title", "Externally changed title"),
    ("url", "https://example.com/changed"),
])
def test_manual_replay_conflicting_identity_stops_without_business_write(ingestion, field, value):
    kernel, service, storage, transport, _, _ = ingestion
    spec = {"title": "Manual original", "url": "https://example.com/original"}
    original = complete(kernel, service.controls.enqueue_add("original", spec)["pipeline_run_id"])
    assert original["status"] == "completed"
    row = storage.list("hotspots")[0]
    # External fixture corruption, through actual repository/HTTP, after the original save.
    storage.update("hotspots", row["hotspot_id"], {field: value})
    before = deepcopy(storage.list("hotspots"))
    offset = len(transport.calls)
    run = complete(kernel, service.controls.enqueue_add("new-key-same-content", spec)["pipeline_run_id"])
    assert run["status"] == "blocked" and run["steps"][0]["status"] == "blocked"
    assert run["steps"][0]["error_message"] == "AmbiguousWrite: reconciliation required"
    assert storage.list("hotspots") == before
    assert writes(transport, offset) == []
    assert kernel.telemetry.list(run_id=run["pipeline_run_id"])[-1]["failure_class"] == "AmbiguousWrite"
    assert kernel.telemetry.usage(run_id=run["pipeline_run_id"])["attempts"] == 0


def test_duplicate_manual_dedupe_identity_blocks_without_picking_or_creating_a_row(ingestion):
    kernel, service, storage, transport, _, _ = ingestion
    spec = {"title": "Duplicate manual", "url": "https://example.com/manual"}
    assert complete(kernel, service.controls.enqueue_add("first", spec)["pipeline_run_id"])["status"] == "completed"
    row = storage.list("hotspots")[0]
    storage.ensure("hotspots", {**row, "hotspot_id": "external-conflicting-business-id"})
    before = deepcopy(storage.list("hotspots"))
    assert len(before) == 2
    offset = len(transport.calls)
    run = complete(kernel, service.controls.enqueue_add("second", spec)["pipeline_run_id"])
    assert run["status"] == "blocked" and run["steps"][0]["status"] == "blocked"
    assert storage.list("hotspots") == before and writes(transport, offset) == []
    assert kernel.telemetry.list(run_id=run["pipeline_run_id"])[-1]["failure_class"] == "AmbiguousWrite"


def test_discard_target_deleted_after_enqueue_fails_without_resurrecting_source(ingestion):
    kernel, service, storage, transport, _, _ = ingestion
    spec = {"title": "Delete after enqueue"}
    assert complete(kernel, service.controls.enqueue_add("first", spec)["pipeline_run_id"])["status"] == "completed"
    row = storage.list("hotspots")[0]
    run_id = service.controls.enqueue_discard(row["hotspot_id"], "discard", "normalized")["pipeline_run_id"]
    storage.delete("hotspots", row["hotspot_id"])
    offset = len(transport.calls)
    run = complete(kernel, run_id)
    assert run["status"] == "failed" and run["steps"][0]["status"] == "failed"
    assert run["steps"][0]["error_message"] == "MissingRecord: handler failed"
    assert storage.list("hotspots") == [] and writes(transport, offset) == []
    assert all(t["failure_class"] == "MissingRecord" for t in kernel.telemetry.list(run_id=run_id))
