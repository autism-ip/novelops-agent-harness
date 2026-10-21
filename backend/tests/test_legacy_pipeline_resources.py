"""
[INPUT]: 实际 create_app、Settings、FeishuClient、Repository 和 PipelineEngine；仅控制出站 HTTP。
[OUTPUT]: 兼容管线 API 的配置隔离、资源释放、鉴权与失败回滚行为门禁。
[POS]: ZEN-104 保留兼容路径的 HTTP 集成验收，不代表真实飞书或 v0.2 调度验收。
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import copy
import json
import os
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.feishu_transport import FeishuTransport


BODY = {"pipeline_type": "compatibility", "steps": [
    {"step_key": "first", "assigned_agent_id": "synthetic-agent"},
    {"step_key": "second", "assigned_agent_id": "synthetic-agent", "depends_on": ["first"]},
]}
ROUTES = [("POST", "/api/pipelines"), ("GET", "/api/pipelines/PR-existing"),
          ("GET", "/api/pipelines/PR-existing/steps")]


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    for name in list(os.environ):
        if name.startswith("FEISHU_") or name == "BACKEND_API_KEY":
            monkeypatch.delenv(name, raising=False)
    http_clients = []
    test_clients = []
    transport = FeishuTransport()
    network = SimpleNamespace(handler=transport)
    real_client = httpx.Client

    def build(source="explicit", *, missing="", kernel=None):
        values = {"BACKEND_API_KEY": "synthetic-api-key", "FEISHU_APP_ID": "synthetic-app",
                  "FEISHU_APP_SECRET": "synthetic-secret", "FEISHU_APP_TOKEN": "configured-base",
                  "FEISHU_TABLE_ID_PIPELINE_RUNS": "configured-pipelines",
                  "FEISHU_TABLE_ID_STEP_RUNS": "configured-steps"}
        if missing:
            values[missing] = ""
        if source == "dotenv":
            path = tmp_path / "synthetic.env"
            path.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
            settings = Settings(_env_file=path, HARNESS_ENABLED=False)
        elif source == "process":
            for key, value in values.items():
                monkeypatch.setenv(key, value)
            settings = Settings(_env_file=None, HARNESS_ENABLED=False)
        else:
            settings = Settings(_env_file=None, HARNESS_ENABLED=False, **values)
            # Deliberately conflicting process configuration cannot redirect this app.
            for key in values:
                if key.startswith("FEISHU_"):
                    monkeypatch.setenv(key, "ambient-other-" + key.lower())
        app = create_app(settings, kernel=kernel)
        test_client = TestClient(app)
        test_clients.append(test_client)

        def external_client(*args, **kwargs):
            client = real_client(*args, transport=httpx.MockTransport(lambda req: network.handler(req)), **kwargs)
            http_clients.append(client)
            return client

        monkeypatch.setattr("app.feishu.client.httpx.Client", external_client)
        return SimpleNamespace(http=test_client, settings=settings, app=app,
            headers={"x-api-key": settings.BACKEND_API_KEY})

    yield SimpleNamespace(build=build, transport=transport, clients=http_clients, network=network)
    for client in test_clients:
        client.close()
    for client in http_clients:
        client.close()


def seed(transport, *, duplicate=False):
    row = {"record_id": "rec-existing", "fields": {"pipeline_run_id": "PR-existing",
        "pipeline_type": "compatibility", "status": "pending"}}
    transport.tables["configured-pipelines"] = {"rec-existing": row}
    if duplicate:
        transport.tables["configured-pipelines"]["rec-duplicate"] = {
            "record_id": "rec-duplicate", "fields": dict(row["fields"])}
    transport.tables["configured-steps"] = {"rec-step": {"record_id": "rec-step", "fields": {
        "step_run_id": "SR-existing", "pipeline_run_id": "PR-existing", "step_key": "first",
        "status": "pending"}}}


def request(app, method, path, *, body=BODY, authorized=True):
    return app.http.request(method, path, json=body if method == "POST" else None,
                            headers=app.headers if authorized else {})


@pytest.mark.parametrize("source", ["dotenv", "explicit", "process"])
@pytest.mark.parametrize("method,path", ROUTES)
def test_resolved_settings_control_real_pipeline_http_io(fixture, source, method, path):
    app = fixture.build(source)
    seed(fixture.transport)
    environment = dict(os.environ)
    response = request(app, method, path)
    assert response.status_code == (201 if method == "POST" else 200), response.text
    if method == "POST":
        pipeline_id = response.json()["pipeline_run_id"]
        rows = fixture.transport.tables["configured-pipelines"].values()
        created = [row for row in rows if row["fields"]["pipeline_run_id"] == pipeline_id]
        assert len(created) == 1 and created[0]["record_id"] != pipeline_id
        steps = [row["fields"] for row in fixture.transport.tables["configured-steps"].values()
                 if row["fields"]["pipeline_run_id"] == pipeline_id]
        assert [row["step_key"] for row in steps] == ["first", "second"]
        assert steps[1]["depends_on"] == "first"
    else:
        data = response.json()
        if path.endswith("/steps"):
            assert data[0]["step_run_id"] == "SR-existing"
        else:
            assert data["record_id"] == "rec-existing"
            assert data["step_runs"][0]["step_run_id"] == "SR-existing"
    auth = [call for call in fixture.transport.calls if "/auth/" in call.url.path]
    assert json.loads(auth[0].content) == {
        "app_id": "synthetic-app", "app_secret": "synthetic-secret"}
    assert all("/apps/configured-base/tables/configured-" in call.url.path
               for call in fixture.transport.calls if "/auth/" not in call.url.path)
    assert dict(os.environ) == environment
    assert len(fixture.clients) == 1 and fixture.clients[0].is_closed


@pytest.mark.parametrize("case,status", [
    ("created", 201), ("read", 200), ("steps", 200), ("missing", 404), ("duplicate", 409),
    ("invalid", 422), ("upstream_read", 503), ("upstream_create", 503), ("missing_table", 422),
])
def test_request_resources_close_on_success_and_failure(fixture, case, status):
    app = fixture.build("process", missing="FEISHU_TABLE_ID_STEP_RUNS" if case == "missing_table" else "")
    seed(fixture.transport, duplicate=case == "duplicate")
    before = copy.deepcopy(fixture.transport.tables)
    method, path, body = "GET", "/api/pipelines/PR-existing", BODY
    if case in {"created", "invalid", "upstream_create", "missing_table"}:
        method, path = "POST", "/api/pipelines"
    if case == "invalid":
        body = {**BODY, "steps": []}
    if case == "steps":
        path += "/steps"
    if case == "missing":
        path = "/api/pipelines/PR-absent"
    if case == "upstream_create":
        fixture.transport.fail_create = "configured-steps"
    if case == "upstream_read":
        original = fixture.transport.__call__

        def failed_read(outbound):
            if "/auth/" in outbound.url.path:
                return original(outbound)
            fixture.transport.calls.append(outbound)
            return httpx.Response(400, json={"code": 123, "msg": "synthetic unavailable"})

        # Change only the external HTTP boundary, preserving real lookup/error mapping.
        fixture.network.handler = failed_read
    response = request(app, method, path, body=body)
    assert response.status_code == status, response.text
    assert len(fixture.clients) == 1 and fixture.clients[0].is_closed
    if case not in {"created"}:
        assert fixture.transport.tables == before
    if case in {"invalid", "missing_table"}:
        assert fixture.transport.calls == []
    if status == 503:
        assert response.json() == {"detail": "FeishuAPIError", "reconciliation_required": True}
        assert "synthetic-secret" not in response.text


@pytest.mark.parametrize("method,path", ROUTES)
def test_unauthorized_legacy_routes_create_no_external_client(fixture, method, path):
    app = fixture.build("process")
    response = request(app, method, path, authorized=False)
    assert response.status_code == 401
    assert fixture.clients == [] and fixture.transport.calls == []


def test_active_kernel_disables_legacy_creation_before_external_io(fixture):
    app = fixture.build("process", kernel=object())
    response = request(app, "POST", "/api/pipelines")
    assert response.status_code == 410
    assert response.json()["detail"] == "Use /api/workflows for v0.2 execution"
    assert fixture.clients == [] and fixture.transport.calls == []
