"""Integration tests for NovelOps API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def settings(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "secret")
    return Settings()


@pytest.fixture()
def client(settings):
    app = create_app(settings)
    return TestClient(app)


# --- Health & Status ---


def test_health_returns_ok(client):
    r = client.get("/api/system/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"


def test_status_returns_component_status(client):
    r = client.get("/api/system/status")
    assert r.status_code == 200
    assert r.json()["backend_status"] == "running"


# --- API Key Guard ---


def test_public_endpoints_accessible_when_key_is_set(client):
    r = client.get("/api/system/health")
    assert r.status_code == 200
    r = client.get("/api/system/status")
    assert r.status_code == 200


def test_guard_rejects_missing_key(client):
    r = client.get("/api/system/config")
    assert r.status_code == 401


def test_guard_rejects_wrong_key(client):
    r = client.get("/api/system/config", headers={"x-api-key": "wrong"})
    assert r.status_code == 401


def test_guard_accepts_correct_key(client):
    r = client.get("/api/system/config", headers={"x-api-key": "secret"})
    assert r.status_code == 200
