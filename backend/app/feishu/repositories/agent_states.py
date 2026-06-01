"""
[INPUT]: 依赖 app.feishu.repositories.base.BaseRepository 的 CRUD 能力
[OUTPUT]: 对外提供 AgentStatesRepo 类
[POS]: repositories 包的具体实现，封装 AgentStates 表的 CRUD 与领域查询
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository


# ============================================================
# agent states repository
# ============================================================


class AgentStatesRepo(BaseRepository):
    """Repository for the AgentStates table."""

    def __init__(self, client: FeishuClient, app_token: str, table_id: str) -> None:
        from app.feishu.table_map import FIELD_MAPS

        super().__init__(client, app_token, table_id, FIELD_MAPS["agent_states"])

    # ----------------------------------------------------------
    # domain queries
    # ----------------------------------------------------------

    def find_by_agent(self, agent_id: str) -> list[dict]:
        """Return states for a specific agent."""
        return self.list(filter_expr=f'CurrentValue.[agent_id] = "{agent_id}"')

    def find_by_status(self, status: str) -> list[dict]:
        """Return states matching *status*."""
        return self.list(filter_expr=f'CurrentValue.[status] = "{status}"')
