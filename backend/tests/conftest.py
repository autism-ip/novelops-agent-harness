"""
[INPUT]: 依赖 pytest、httpx ASGITransport 与待实现的 app.main.create_app。
[OUTPUT]: 对外提供 isolated_settings、app、client、auth_headers 测试夹具。
[POS]: tests 的环境隔离层，阻断本机真实密钥污染行为门禁。
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    from app.config import Settings

    secret_values = {
        "BACKEND_API_KEY": "test-key",
        "FEISHU_APP_ID": "feishu-id-secret",
        "FEISHU_APP_SECRET": "feishu-secret-value",
        "LLM_API_KEY": "llm-secret-value",
        "LLM_PROVIDER": "openai",
        "OPENCLI_ENABLED": "false",
        "CORS_ORIGINS": '["https://frontend.example"]',
    }
    for name, value in secret_values.items():
        monkeypatch.setenv(name, value)
    return Settings()


@pytest.fixture
def app(isolated_settings: Settings):
    from app.main import create_app

    return create_app(isolated_settings)


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(isolated_settings: Settings) -> dict[str, str]:
    return {"x-api-key": isolated_settings.BACKEND_API_KEY}
