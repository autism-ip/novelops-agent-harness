"""
[INPUT]: 依赖 app.feishu.repositories.base.BaseRepository 的 CRUD 能力
[OUTPUT]: 对外提供 BooksRepo 类
[POS]: repositories 包的具体实现，封装 Books 表的 CRUD 与领域查询
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository


# ============================================================
# books repository
# ============================================================


class BooksRepo(BaseRepository):
    """Repository for the Books table."""

    def __init__(self, client: FeishuClient, app_token: str, table_id: str) -> None:
        from app.feishu.table_map import FIELD_MAPS

        super().__init__(client, app_token, table_id, FIELD_MAPS["books"])

    # ----------------------------------------------------------
    # domain queries
    # ----------------------------------------------------------

    def find_by_status(self, status: str) -> list[dict]:
        """Return books matching *status*."""
        return self.list(filter_expr=self._field_filter(status=status))
