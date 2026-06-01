"""
[INPUT]: 依赖 httpx AsyncClient 夹具与 APIKeyMiddleware 契约。
[OUTPUT]: 对外提供 API key 鉴权行为测试。
[POS]: tests 的安全门禁，确保未授权请求在路由缺失前被拒绝。
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""


async def test_health_and_status_are_public_probe_endpoints(client):
    health = await client.get("/api/system/health")
    status = await client.get("/api/system/status")

    assert health.status_code == 200
    assert status.status_code == 200


async def test_missing_api_key_is_rejected_before_private_route_resolution(client):
    response = await client.get("/api/pipelines")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


async def test_wrong_api_key_is_rejected(client):
    response = await client.get("/api/pipelines", headers={"x-api-key": "wrong"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


async def test_valid_api_key_passes_middleware_to_application(client, auth_headers):
    response = await client.get("/api/pipelines", headers=auth_headers)

    assert response.status_code != 401
    assert response.status_code == 404
