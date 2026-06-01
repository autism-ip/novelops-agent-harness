"""
[INPUT]: 依赖 httpx AsyncClient 夹具与 ZEN-28 系统端点契约。
[OUTPUT]: 对外提供系统端点行为测试。
[POS]: tests 的观测门禁，确保响应语义稳定且不回显密钥。
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

import pytest

pytestmark = pytest.mark.asyncio

SECRET_SENTINELS = (
    "test-key",
    "feishu-id-secret",
    "feishu-secret-value",
    "llm-secret-value",
)


async def test_health_returns_exact_liveness_contract(client):
    response = await client.get("/api/system/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


async def test_status_returns_component_placeholders_not_fake_success(client):
    response = await client.get("/api/system/status")

    assert response.status_code == 200
    assert response.json() == {
        "backend_status": "running",
        "worker_status": "not_started",
        "feishu_status": "not_configured",
        "opencli_status": "not_configured",
        "active_pipeline_runs": 0,
        "pending_steps": 0,
        "failed_steps": 0,
    }


async def test_public_system_responses_do_not_expose_backend_secrets(client):
    for path in ("/api/system/health", "/api/system/status"):
        response = await client.get(path)
        body = response.text

        assert response.status_code == 200
        assert all(secret not in body for secret in SECRET_SENTINELS)


async def test_config_endpoint_is_protected_and_sanitized(client, auth_headers):
    unauthorized = await client.get("/api/system/config")
    authorized = await client.get("/api/system/config", headers=auth_headers)

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json() == {
        "llm_provider": "openai",
        "opencli_enabled": False,
        "cors_origins": ["https://frontend.example"],
    }
    assert all(secret not in authorized.text for secret in SECRET_SENTINELS)
