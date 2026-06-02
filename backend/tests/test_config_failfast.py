"""
[INPUT]: 依赖 app.feishu.table_map.TableMapConfig
[OUTPUT]: 对外提供 get_table_id fail-fast 行为级测试
[POS]: tests 的配置门禁，验证缺失环境变量时立即报错
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import pytest

from app.feishu.table_map import TableMapConfig


# ============================================================
# get_table_id — fail-fast
# ============================================================


class TestGetTableIdFailFast:
    """get_table_id raises ValueError when env var is missing."""

    def test_raises_on_missing_env(self) -> None:
        cfg = TableMapConfig()
        with pytest.raises(ValueError, match="Missing environment variable"):
            cfg.get_table_id("agents")

    def test_success_when_env_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FEISHU_TABLE_ID_AGENTS", "tbl_real")
        cfg = TableMapConfig()
        assert cfg.get_table_id("agents") == "tbl_real"

    def test_constructor_arg(self) -> None:
        cfg = TableMapConfig(app_token="bascn_custom")
        assert cfg.app_token == "bascn_custom"

    def test_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FEISHU_APP_TOKEN", "bascn_env")
        cfg = TableMapConfig()
        assert cfg.app_token == "bascn_env"
