"""
[INPUT]: 依赖 app.feishu.repositories.base.BaseRepository 的 CRUD 能力
[OUTPUT]: 对外提供 ReviewReportsRepo 类
[POS]: repositories 包的具体实现，封装 ReviewReports 表的 CRUD 与领域查询
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository


# ============================================================
# review reports repository
# ============================================================


class ReviewReportsRepo(BaseRepository):
    """Repository for the ReviewReports table."""

    def __init__(self, client: FeishuClient, app_token: str, table_id: str) -> None:
        from app.feishu.table_map import FIELD_MAPS

        super().__init__(client, app_token, table_id, FIELD_MAPS["review_reports"])

    # ----------------------------------------------------------
    # domain queries
    # ----------------------------------------------------------

    def find_by_target(self, target_type: str, target_id: str) -> list[dict]:
        """Return review reports for a specific target."""
        return self.list(
            filter_expr=(
                f'CurrentValue.[target_type] = "{target_type}"'
                f' && CurrentValue.[target_id] = "{target_id}"'
            )
        )
