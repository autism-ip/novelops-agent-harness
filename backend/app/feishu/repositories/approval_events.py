"""
[INPUT]: 依赖 app.feishu.repositories.base.BaseRepository 的 CRUD 能力
[OUTPUT]: 对外提供 ApprovalEventsRepo 类
[POS]: repositories 包的具体实现，封装 ApprovalEvents 表的 CRUD 与领域查询
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository


# ============================================================
# approval events repository
# ============================================================


class ApprovalEventsRepo(BaseRepository):
    """Repository for the ApprovalEvents table."""

    def __init__(self, client: FeishuClient, app_token: str, table_id: str) -> None:
        from app.feishu.table_map import FIELD_MAPS

        super().__init__(client, app_token, table_id, FIELD_MAPS["approval_events"])

    # ----------------------------------------------------------
    # domain queries
    # ----------------------------------------------------------

    def find_by_target(self, target_type: str, target_id: str) -> list[dict]:
        """Return approval events for a specific target."""
        return self.list(
            filter_expr=self._field_filter(target_type=target_type, target_id=target_id)
        )
