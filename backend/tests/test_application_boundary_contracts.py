"""
[INPUT]: Actual app factory, middleware, Settings dependency, runtime composition and compatibility router.
[OUTPUT]: Application isolation, safe invalid configuration, status recovery and request resource contracts.
[POS]: Draft ZEN-104 HTTP/composition boundaries; isolated legacy router is not mounted production health.
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.deps import get_settings
from app.api.routes.health import router as compatibility_health_router
from app.config import Settings
from app.harness import HarnessKernel
from app.main import create_app
from app.runtime import build_runtime
from tests.feishu_transport import make_storage


@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_blank_api_key_is_rejected_before_an_application_can_be_created(value):
    with pytest.raises(ValidationError, match="BACKEND_API_KEY must not be blank"):
        Settings(_env_file=None, BACKEND_API_KEY=value)


def test_missing_api_key_does_not_fall_back_to_an_unsafe_default(monkeypatch):
    monkeypatch.delenv("BACKEND_API_KEY", raising=False)
    with pytest.raises(ValidationError, match="Field required"):
        Settings(_env_file=None)


def test_real_dependency_and_auth_guard_use_the_same_application_settings_instance(monkeypatch):
    pairs = []
    for label in ("first", "second"):
        settings = Settings(_env_file=None, BACKEND_API_KEY=label + "-synthetic-key",
                            LLM_PROVIDER=label + "-synthetic-provider", HARNESS_ENABLED=False)
        app = create_app(settings)

        @app.get("/api/settings-contract")
        def selected_settings(resolved: Settings = Depends(get_settings)):
            return {"provider": resolved.LLM_PROVIDER}

        pairs.append((app, settings))
    monkeypatch.setenv("BACKEND_API_KEY", "ambient-unrelated-key")
    monkeypatch.setenv("LLM_PROVIDER", "ambient-unrelated-provider")
    for app, settings in pairs:
        with TestClient(app) as client:
            assert client.get("/api/settings-contract").status_code == 401
            assert client.get("/api/settings-contract", headers={"x-api-key": "ambient-unrelated-key"}).status_code == 401
            response = client.get("/api/settings-contract", headers={"x-api-key": settings.BACKEND_API_KEY})
            assert response.status_code == 200
            assert response.json() == {"provider": settings.LLM_PROVIDER}
            other = next(value for _, value in pairs if value is not settings)
            assert client.get("/api/settings-contract", headers={"x-api-key": other.BACKEND_API_KEY}).status_code == 401
            assert settings.BACKEND_API_KEY not in response.text
            assert app.state.settings is settings


def test_actual_app_allows_non_api_surface_without_exempting_private_api():
    app = create_app(Settings(_env_file=None, BACKEND_API_KEY="synthetic-key", HARNESS_ENABLED=False))

    @app.get("/outside-contract")
    def outside():
        return {"surface": "outside-api"}

    with TestClient(app) as client:
        assert client.get("/outside-contract").json() == {"surface": "outside-api"}
        assert client.get("/api/system/config").status_code == 401


@pytest.mark.parametrize("path,expected", [
    ("/health", {"status": "ok"}),
    ("/status", {"version": "0.1.0", "status": "running"}),
])
def test_isolated_legacy_health_router_retains_its_imported_consumer_contract(path, expected):
    consumer = FastAPI()
    consumer.include_router(compatibility_health_router)
    with TestClient(consumer) as client:
        response = client.get(path)
    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.parametrize("path", ["/health", "/status"])
def test_legacy_health_router_is_not_mistaken_for_the_mounted_application_surface(path):
    app = create_app(Settings(_env_file=None, BACKEND_API_KEY="synthetic-key", HARNESS_ENABLED=False))
    with TestClient(app) as client:
        assert client.get(path).status_code == 404
        assert client.get("/api/system/health").json()["status"] == "ok"
        assert client.get("/api/system/status").json()["worker_status"] == "not_started"


def test_unknown_lazy_application_attribute_raises_without_constructing_settings(monkeypatch):
    import app.main as entrypoint
    monkeypatch.delenv("BACKEND_API_KEY", raising=False)
    with pytest.raises(AttributeError, match="no attribute 'not_a_public_app'"):
        getattr(entrypoint, "not_a_public_app")


@pytest.mark.parametrize("missing", ["PIPELINE_RUNS", "STEP_RUNS", "APPROVAL_EVENTS"])
def test_actual_runtime_closes_http_client_after_required_table_configuration_failure(monkeypatch, missing):
    real_client = httpx.Client
    clients, calls = [], []

    def no_remote(request):
        calls.append(request)
        raise AssertionError("Invalid startup configuration must not send remote HTTP")

    def external_client(*args, **kwargs):
        client = real_client(*args, transport=httpx.MockTransport(no_remote), **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr("app.feishu.client.httpx.Client", external_client)
    values = {"FEISHU_TABLE_ID_" + name: "synthetic-" + name.lower()
              for name in ("PIPELINE_RUNS", "STEP_RUNS", "APPROVAL_EVENTS")}
    values["FEISHU_TABLE_ID_" + missing] = ""
    settings = Settings(_env_file=None, BACKEND_API_KEY="synthetic-key", FEISHU_APP_ID="synthetic-app",
        FEISHU_APP_SECRET="synthetic-secret", FEISHU_APP_TOKEN="synthetic-base", HARNESS_ENABLED=True, **values)
    with pytest.raises(ValueError, match="FEISHU_TABLE_ID_" + missing):
        build_runtime(settings)
    assert len(clients) == 1 and clients[0].is_closed
    assert calls == []


def test_public_status_survives_actual_disposable_metrics_failure_and_recovers(tmp_path):
    storage, transport, external = make_storage()
    kernel = HarnessKernel(storage, journal_dir=tmp_path / "journal")
    original = kernel._counts
    app = create_app(Settings(_env_file=None, BACKEND_API_KEY="synthetic-key", HARNESS_ENABLED=False), kernel=kernel)
    # Do not run lifespan/scheduler: this is the HTTP status fallback boundary.
    client = TestClient(app)
    try:
        kernel._counts = None
        assert kernel.running is False
        response = client.get("/api/system/status")
        assert response.status_code == 200
        assert response.json()["backend_status"] == "running"
        assert response.json()["worker_status"] == "stopped"
        assert response.json()["feishu_status"] == "unreachable"
        assert "TypeError" not in response.text
        assert client.get("/api/system/health").json()["status"] == "ok"
        kernel._counts = original
        recovered = client.get("/api/system/status")
        assert recovered.status_code == 200
        assert recovered.json()["feishu_status"] == "connected"
        assert recovered.json()["worker_status"] == "stopped"
        assert transport.calls == []
    finally:
        kernel._counts = original
        client.close()
        external._http.close()
