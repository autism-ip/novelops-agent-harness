"""
[INPUT]: 依赖 app.feishu.table_map 的 TABLE_NAMES、FIELD_MAPS、TableMapConfig
[OUTPUT]: 对外提供 table_map 的行为级测试用例——表数量、映射完整性、环境变量覆盖
[POS]: tests 的 table_map 门禁，验证 16 张表配置的完整性与运行时解析行为
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import pytest

from app.feishu.table_map import FIELD_MAPS, TABLE_NAMES, TableMapConfig


# ============================================================
# constants integrity
# ============================================================


EXPECTED_TABLE_COUNT = 16


class TestTableNames:
    """TABLE_NAMES defines exactly 16 logical tables."""

    def test_count(self) -> None:
        assert len(TABLE_NAMES) == EXPECTED_TABLE_COUNT

    def test_known_keys(self) -> None:
        expected = {
            "agents", "agent_states", "agent_runs", "pipeline_runs",
            "step_runs", "hotspots", "hotspot_analyses", "title_candidates",
            "cover_plans", "books", "chapter_briefs", "chapter_versions",
            "review_reports", "revision_tasks", "agent_team_snapshots",
            "approval_events",
        }
        assert set(TABLE_NAMES.keys()) == expected


class TestFieldMaps:
    """FIELD_MAPS defines exactly 16 table mappings."""

    def test_count(self) -> None:
        assert len(FIELD_MAPS) == EXPECTED_TABLE_COUNT

    def test_every_table_name_has_field_map(self) -> None:
        """Every key in TABLE_NAMES must have a corresponding FIELD_MAPS entry."""
        for name in TABLE_NAMES:
            assert name in FIELD_MAPS, f"Missing FIELD_MAPS entry for '{name}'"

    def test_no_extra_field_maps(self) -> None:
        """FIELD_MAPS must not contain tables absent from TABLE_NAMES."""
        for name in FIELD_MAPS:
            assert name in TABLE_NAMES, f"Extra FIELD_MAPS entry '{name}' not in TABLE_NAMES"

    def test_agents_fields(self) -> None:
        """Spot-check: agents table has expected field set."""
        fields = FIELD_MAPS["agents"]
        assert "agent_id" in fields
        assert "agent_name" in fields
        assert "agent_role" in fields
        assert "enabled" in fields

    def test_books_fields(self) -> None:
        """Spot-check: books table has expected field set."""
        fields = FIELD_MAPS["books"]
        assert "book_id" in fields
        assert "book_title" in fields
        assert "genre" in fields
        assert "status" in fields


# ============================================================
# TableMapConfig — get_table_id
# ============================================================


class TestGetTableId:
    """get_table_id resolves table IDs from env or raises ValueError."""

    def test_raises_on_missing_env(self) -> None:
        """Without env var, raises ValueError with clear message."""
        cfg = TableMapConfig()
        with pytest.raises(ValueError, match="Missing environment variable"):
            cfg.get_table_id("agents")
        with pytest.raises(ValueError, match="Missing environment variable"):
            cfg.get_table_id("books")

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env var FEISHU_TABLE_ID_<UPPER> takes priority."""
        monkeypatch.setenv("FEISHU_TABLE_ID_AGENTS", "tbl_custom_agents")
        cfg = TableMapConfig()
        assert cfg.get_table_id("agents") == "tbl_custom_agents"

    def test_env_var_case_sensitivity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env key uses UPPER_SNAKE of the logical name."""
        monkeypatch.setenv("FEISHU_TABLE_ID_HOTSPOT_ANALYSES", "tbl_ha_99")
        cfg = TableMapConfig()
        assert cfg.get_table_id("hotspot_analyses") == "tbl_ha_99"


# ============================================================
# TableMapConfig — get_field_map
# ============================================================


class TestGetFieldMap:
    """get_field_map returns the correct mapping dict."""

    def test_returns_field_map(self) -> None:
        cfg = TableMapConfig()
        fm = cfg.get_field_map("books")
        assert fm["book_id"] == "book_id"
        assert fm["book_title"] == "book_title"

    def test_unknown_table_raises(self) -> None:
        cfg = TableMapConfig()
        with pytest.raises(KeyError, match="Unknown table"):
            cfg.get_field_map("nonexistent_table")


# ============================================================
# TableMapConfig — app_token
# ============================================================


class TestAppToken:
    """app_token is resolved from constructor arg or env var."""

    def test_constructor_arg(self) -> None:
        cfg = TableMapConfig(app_token="bascn_custom")
        assert cfg.app_token == "bascn_custom"

    def test_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FEISHU_APP_TOKEN", "bascn_env")
        cfg = TableMapConfig()
        assert cfg.app_token == "bascn_env"

    def test_default_empty(self) -> None:
        cfg = TableMapConfig()
        assert cfg.app_token == ""
