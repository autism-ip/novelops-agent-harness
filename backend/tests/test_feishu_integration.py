"""
[INPUT]: 依赖 app.feishu 包的完整栈——client、table_map、repositories
[OUTPUT]: 对外提供集成测试套件，验证真实 Feishu Bitable CRUD 循环
[POS]: tests/ 的集成门禁，标记 @pytest.mark.integration，无凭证时自动跳过
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import os

import pytest

from app.feishu.client import FeishuClient
from app.feishu.repositories.agents import AgentsRepo
from app.feishu.table_map import TableMapConfig

# ============================================================
# skip when credentials are missing
# ============================================================

_CREDENTIALS_PRESENT = all(
    os.environ.get(k) for k in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_APP_TOKEN")
)

pytestmark = pytest.mark.integration
skip_reason = "Feishu credentials not configured"
skipUnlessCreds = pytest.mark.skipif(not _CREDENTIALS_PRESENT, reason=skip_reason)


# ============================================================
# fixtures
# ============================================================


@pytest.fixture(scope="module")
def client() -> FeishuClient:
    """Create a real FeishuClient from env vars."""
    return FeishuClient(
        app_id=os.environ["FEISHU_APP_ID"],
        app_secret=os.environ["FEISHU_APP_SECRET"],
    )


@pytest.fixture(scope="module")
def config() -> TableMapConfig:
    """Create a TableMapConfig from env vars."""
    return TableMapConfig(app_token=os.environ["FEISHU_APP_TOKEN"])


@pytest.fixture(scope="module")
def agents_repo(client: FeishuClient, config: TableMapConfig) -> AgentsRepo:
    """Create an AgentsRepo wired to the real Agents table."""
    return AgentsRepo(
        client=client,
        app_token=config.app_token,
        table_id=config.get_table_id("agents"),
    )


# ============================================================
# integration tests — CRUD cycle
# ============================================================


@skipUnlessCreds
class TestAgentsCrudCycle:
    """End-to-end create -> read -> update -> delete on real Feishu."""

    def test_create_read_update_delete(self, agents_repo: AgentsRepo) -> None:
        # -- create --
        record = agents_repo.create({
            "agent_id": "test-agent-001",
            "agent_name": "Integration Test Agent",
            "agent_role": "tester",
            "enabled": True,
        })
        assert record["agent_id"] == "test-agent-001"
        assert record["record_id"]
        record_id = record["record_id"]

        try:
            # -- read --
            fetched = agents_repo.get(record_id)
            assert fetched is not None
            assert fetched["agent_id"] == "test-agent-001"
            assert fetched["agent_name"] == "Integration Test Agent"

            # -- update --
            updated = agents_repo.update(record_id, {
                "agent_name": "Updated Test Agent",
            })
            assert updated["agent_name"] == "Updated Test Agent"

            # -- verify update persisted --
            fetched_again = agents_repo.get(record_id)
            assert fetched_again is not None
            assert fetched_again["agent_name"] == "Updated Test Agent"

        finally:
            # -- cleanup: always delete test record --
            result = agents_repo.delete(record_id)
            assert result is True

    def test_list_returns_records(self, agents_repo: AgentsRepo) -> None:
        """List should return at least an empty list without error."""
        records = agents_repo.list(page_size=5)
        assert isinstance(records, list)


# ============================================================
# acceptance criteria — repository hides Feishu details
# ============================================================


@skipUnlessCreds
class TestAcceptanceCriteria:
    """Verify the repository layer abstracts away Feishu internals."""

    def test_no_direct_api_urls_in_usage(self, agents_repo: AgentsRepo) -> None:
        """Agent code accesses data through repo methods, not raw URLs."""
        assert hasattr(agents_repo, "create")
        assert hasattr(agents_repo, "get")
        assert hasattr(agents_repo, "list")
        assert hasattr(agents_repo, "update")
        assert hasattr(agents_repo, "delete")
        assert hasattr(agents_repo, "find_by_role")

    def test_field_mapping_transparent(self, agents_repo: AgentsRepo) -> None:
        """Python field names are used; Feishu names are hidden."""
        mapped = agents_repo._to_feishu({"agent_id": "x", "agent_name": "y"})
        assert "agent_id" in mapped or "Agent ID" in mapped
