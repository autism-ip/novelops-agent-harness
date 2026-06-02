"""
[INPUT]: 依赖 app.feishu.repositories.base.BaseRepository 的 CRUD 能力
[OUTPUT]: 对外提供 PipelineRunsRepo 类
[POS]: repositories 包的具体实现，封装 PipelineRuns 表的 CRUD 与领域查询
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository


# ============================================================
# pipeline runs repository
# ============================================================


class PipelineRunsRepo(BaseRepository):
    """Repository for the PipelineRuns table."""

    def __init__(self, client: FeishuClient, app_token: str, table_id: str) -> None:
        from app.feishu.table_map import FIELD_MAPS

        super().__init__(client, app_token, table_id, FIELD_MAPS["pipeline_runs"])

    # ----------------------------------------------------------
    # domain queries
    # ----------------------------------------------------------

    def find_by_status(self, status: str) -> list[dict]:
        """Return pipeline runs matching *status*."""
        return self.list(filter_expr=f'CurrentValue.[status] = "{status}"')

    def find_by_type(self, pipeline_type: str) -> list[dict]:
        """Return pipeline runs of a specific *pipeline_type*."""
        return self.list(
            filter_expr=f'CurrentValue.[pipeline_type] = "{pipeline_type}"'
        )
