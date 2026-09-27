"""Stateful HTTP fixture: actual client/repos, distinct Feishu/domain IDs."""
import json
import re

import httpx

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository
from app.feishu.table_map import FIELD_MAPS
from app.storage import FeishuStorageProvider


class FeishuTransport:
    def __init__(self):
        self.tables = {}
        self.next_id = 0
        self.calls = []
        self.fail_create = None

    def __call__(self, request):
        self.calls.append(request)
        parts = request.url.path.split("/")
        if "auth" in parts:
            return httpx.Response(200, json={"code": 0, "tenant_access_token": "test", "expire": 7200})
        table = parts[parts.index("tables") + 1]
        rows = self.tables.setdefault(table, {})
        record_id = parts[-1] if parts[-1] != "records" else None
        if request.method == "POST":
            if self.fail_create == table:
                self.fail_create = None
                return httpx.Response(400, json={"code": 123, "msg": "fixture failure"})
            self.next_id += 1
            record_id = f"rec{self.next_id}"
            rows[record_id] = {"record_id": record_id, "fields": json.loads(request.content)["fields"]}
        elif request.method == "PUT":
            assert record_id in rows, f"Domain ID leaked into storage path: {record_id}"
            rows[record_id]["fields"].update(json.loads(request.content)["fields"])
        elif request.method == "DELETE":
            assert record_id in rows, f"Domain ID leaked into storage path: {record_id}"
            del rows[record_id]
            return httpx.Response(200, json={"code": 0, "data": {}})
        elif record_id is None:
            matches = list(rows.values())
            for field, value in re.findall(r'CurrentValue\.\[([^]]+)\] = ("(?:\\.|[^"\\])*"|\d+)', request.url.params.get("filter", "")):
                matches = [r for r in matches if r["fields"].get(field) == json.loads(value)]
            return httpx.Response(200, json={"code": 0, "data": {"items": matches, "has_more": False}})
        if record_id not in rows:
            return httpx.Response(200, json={"code": 1254043})
        return httpx.Response(200, json={"code": 0, "data": {"record": rows[record_id]}})


def make_storage():
    transport = FeishuTransport()
    client = FeishuClient("fixture-app", "fixture-secret")
    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(transport))
    repos = {name: BaseRepository(client, "app", name, fields) for name, fields in FIELD_MAPS.items()}
    keys = {name: next(iter(fields)) for name, fields in FIELD_MAPS.items()}
    return FeishuStorageProvider(repos, keys), transport, client
