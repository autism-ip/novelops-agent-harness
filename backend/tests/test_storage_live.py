"""Opt-in, destructive CRUD probe for a dedicated test Base only."""
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


@pytest.mark.parametrize("collection,key", [
    ("pipeline_runs", "pipeline_run_id"), ("step_runs", "step_run_id"),
    ("chapter_versions", "version_id"), ("review_reports", "review_id"),
    ("approval_events", "approval_id"),
])
def test_domain_crud_latency(collection, key, record_property):
    client = FeishuClient(os.environ["FEISHU_APP_ID"], os.environ["FEISHU_APP_SECRET"])
    config = TableMapConfig(os.environ["FEISHU_APP_TOKEN"])
    repo = BaseRepository(client, config.app_token, config.get_table_id(collection), FIELD_MAPS[collection])
    provider = FeishuStorageProvider({collection: repo}, {collection: key})
    domain_id = "probe-" + uuid.uuid4().hex
    started = time.monotonic()
    created = False
    try:
        result = provider.ensure(collection, {key: domain_id})
        created = True
        assert result[key] == domain_id
        assert "record_id" not in result
        assert provider.ensure(collection, {key: domain_id}) == result
        assert provider.get(collection, domain_id)[key] == domain_id
        assert provider.update(collection, domain_id, {key: domain_id})[key] == domain_id
        record_property("crud_seconds", time.monotonic() - started)
    finally:
        if created:
            provider.delete(collection, domain_id)
        client._http.close()
