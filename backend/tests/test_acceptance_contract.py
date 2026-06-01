"""
[INPUT]: 依赖 pathlib、pytest 与待实现的 Settings/FastAPI app 工厂。
[OUTPUT]: 对外提供 ZEN-28 验收级结构与配置测试。
[POS]: tests 的 CI 契约门禁，防止项目骨架与计划文档漂移。
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_app_factory_produces_documented_fastapi_metadata(isolated_settings):
    from app.constants import APP_TITLE, APP_VERSION
    from app.main import create_app

    app = create_app(isolated_settings)

    assert app.title == APP_TITLE == "NovelOps Agent Harness"
    assert app.version == APP_VERSION == "0.1.0"
    assert app.state.settings.BACKEND_API_KEY == "test-key"


def test_missing_backend_api_key_fails_with_clear_variable_name(monkeypatch):
    from app.config import Settings

    for name in (
        "BACKEND_API_KEY",
        "FEISHU_APP_ID",
        "FEISHU_APP_SECRET",
        "LLM_API_KEY",
        "LLM_PROVIDER",
        "OPENCLI_ENABLED",
        "CORS_ORIGINS",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    assert "BACKEND_API_KEY" in str(error.value)


def test_zen28_backend_layout_exists_as_executable_source_not_cache_artifacts():
    expected_files = (
        "pyproject.toml",
        ".env.example",
        "app/__init__.py",
        "app/main.py",
        "app/config.py",
        "app/constants.py",
        "app/api/__init__.py",
        "app/api/deps.py",
        "app/api/middleware.py",
        "app/api/routes/__init__.py",
        "app/api/routes/system.py",
        "tests/conftest.py",
        "tests/test_system_endpoints.py",
        "tests/test_api_key_guard.py",
    )

    missing = [path for path in expected_files if not (BACKEND_ROOT / path).is_file()]
    assert missing == []
