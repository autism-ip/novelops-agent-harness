"""
[INPUT]: 依赖 app.feishu.repositories.base.BaseRepository 的 CRUD 能力
[OUTPUT]: 对外提供 ChapterBriefsRepo 类
[POS]: repositories 包的具体实现，封装 ChapterBriefs 表的 CRUD 与领域查询
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository


# ============================================================
# chapter briefs repository
# ============================================================


class ChapterBriefsRepo(BaseRepository):
    """Repository for the ChapterBriefs table."""

    def __init__(self, client: FeishuClient, app_token: str, table_id: str) -> None:
        from app.feishu.table_map import FIELD_MAPS

        super().__init__(client, app_token, table_id, FIELD_MAPS["chapter_briefs"])

    # ----------------------------------------------------------
    # domain queries
    # ----------------------------------------------------------

    def find_by_book(self, book_id: str) -> list[dict]:
        """Return chapter briefs for a specific book."""
        return self.list(filter_expr=self._field_filter(book_id=book_id))
