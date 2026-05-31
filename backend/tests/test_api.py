"""Integration tests for NovelOps API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    return TestClient(app)


# --- Health & Status ---


def test_health_returns_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_status_returns_version(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.1.0"
    assert body["status"] == "running"


# --- API Key Guard ---


def test_guard_passes_when_no_key_configured(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.BACKEND_API_KEY", "")
    r = client.get("/api/health")
    assert r.status_code == 200


def test_guard_rejects_missing_key(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.BACKEND_API_KEY", "secret")
    r = client.get("/api/health")
    assert r.status_code == 401


def test_guard_rejects_wrong_key(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.BACKEND_API_KEY", "secret")
    r = client.get("/api/health", headers={"x-api-key": "wrong"})
    assert r.status_code == 401


def test_guard_accepts_correct_key(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.BACKEND_API_KEY", "secret")
    r = client.get("/api/health", headers={"x-api-key": "secret"})
    assert r.status_code == 200
