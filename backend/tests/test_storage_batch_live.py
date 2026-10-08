"""Opt-in native batch search in an explicitly pinned disposable Base."""
import json
import os
import time
import uuid

import pytest

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository
from app.feishu.table_map import FIELD_MAPS, TableMapConfig
from app.storage import FeishuStorageProvider

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.getenv("FEISHU_FEASIBILITY_LIVE") != "1",
    reason="Requires explicit opt-in and dedicated test Base")]


def test_native_batch_read(tmp_path):
    expected_base = os.environ["FEISHU_FEASIBILITY_EXPECTED_APP_TOKEN"]
    assert expected_base and os.environ["FEISHU_APP_TOKEN"] == expected_base
    config = TableMapConfig(expected_base)
    client = FeishuClient(os.environ["FEISHU_APP_ID"], os.environ["FEISHU_APP_SECRET"])
    collections = ("pipeline_runs", "step_runs")
    keys = {name: next(iter(FIELD_MAPS[name])) for name in collections}
    def provider(http):
        return FeishuStorageProvider({name: BaseRepository(
            http, config.app_token, config.get_table_id(name), FIELD_MAPS[name])
            for name in collections}, keys)
    storage = provider(client)
    prefix = "probe-batch-" + uuid.uuid4().hex
    ids = [prefix + suffix for suffix in ("-first", '-second"\\中文', "-step")]
    rows = [("pipeline_runs", {"pipeline_run_id": ids[0], "status": "pending"}),
            ("pipeline_runs", {"pipeline_run_id": ids[1], "status": "pending"}),
            ("step_runs", {"step_run_id": ids[2], "pipeline_run_id": ids[0],
                           "retry_count": 2, "error_message": '{"text":"中文\\\\value"}'})]
    attempted = []
    calls = []
    client._http.event_hooks["request"].append(calls.append)
    summary = {}
    try:
        for name, row in rows:
            assert storage.get(name, row[keys[name]]) is None, "Refusing to overwrite existing data"
        for name, row in rows:
            attempted.append((name, row[keys[name]]))
            (tmp_path / "batch-cleanup-journal.json").write_text(json.dumps(attempted))
            storage.ensure(name, row)
        calls.clear()
        replay = storage.ensure("pipeline_runs", rows[1][1])
        assert replay["pipeline_run_id"] == ids[1]
        assert len(calls) == 1 and calls[0].url.path.endswith("/records/search")
        summary["special_character_replay_creates"] = 0
        baseline = {row["pipeline_run_id"]: storage.get("pipeline_runs", row["pipeline_run_id"])
                    for name, row in rows if name == "pipeline_runs"}
        calls.clear()
        started = time.monotonic()
        actual = storage.get_many("pipeline_runs", [ids[1], prefix + "-missing", ids[0], ids[1]])
        summary["batch_seconds"] = round(time.monotonic() - started, 3)
        assert actual == baseline and list(actual) == [ids[1], ids[0]]
        assert len(calls) == 1 and calls[0].method == "POST" and calls[0].url.path.endswith("/records/search")
        summary["batch_requests"] = len(calls)
        calls.clear()
        step = storage.get_many("step_runs", [ids[2]])[ids[2]]
        assert step["retry_count"] == 2 and isinstance(step["retry_count"], int)
        assert step["error_message"] == rows[2][1]["error_message"]
        assert "record_id" not in step and len(calls) == 1
        summary["rich_text_and_numeric_roundtrip"] = True
    finally:
        failures = []
        for name, domain_id in reversed(attempted):
            try:
                if storage.get(name, domain_id) is not None:
                    storage.delete(name, domain_id)
            except Exception as error:
                failures.append((name, type(error).__name__))
        client._http.close()
        assert not failures, (failures, str(tmp_path / "batch-cleanup-journal.json"))
    independent = FeishuClient(os.environ["FEISHU_APP_ID"], os.environ["FEISHU_APP_SECRET"])
    try:
        fresh = provider(independent)
        for name in collections:
            assert fresh.get_many(name, [row[keys[name]] for collection, row in rows if collection == name]) == {}
        summary["independent_remaining_rows"] = 0
        print("LIVE BATCH VERIFIED", json.dumps(summary), flush=True)
    finally:
        independent._http.close()
