"""
[INPUT]: 依赖 app.feishu.repositories.base.BaseRepository 的 CRUD 能力
[OUTPUT]: 对外提供 AgentRunsRepo 类
[POS]: repositories 包的具体实现，封装 AgentRuns 表的 CRUD 与领域查询
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository


# ============================================================
# agent runs repository
# ============================================================


class AgentRunsRepo(BaseRepository):
    """Repository for the AgentRuns table."""

    def __init__(self, client: FeishuClient, app_token: str, table_id: str) -> None:
        from app.feishu.table_map import FIELD_MAPS

        super().__init__(client, app_token, table_id, FIELD_MAPS["agent_runs"])

    # ----------------------------------------------------------
    # domain queries
    # ----------------------------------------------------------

    def find_by_agent(self, agent_id: str) -> list[dict]:
        """Return runs for a specific agent."""
        return self.list(filter_expr=self._field_filter(agent_id=agent_id))

    def find_by_pipeline(self, pipeline_run_id: str) -> list[dict]:
        """Return runs belonging to a specific pipeline run."""
        return self.list(
            filter_expr=self._field_filter(pipeline_run_id=pipeline_run_id)
        )
