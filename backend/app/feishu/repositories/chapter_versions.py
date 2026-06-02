"""
[INPUT]: 依赖 app.feishu.repositories.base.BaseRepository 的 CRUD 能力
[OUTPUT]: 对外提供 ChapterVersionsRepo 类
[POS]: repositories 包的具体实现，封装 ChapterVersions 表的 CRUD 与领域查询
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository


# ============================================================
# chapter versions repository
# ============================================================


class ChapterVersionsRepo(BaseRepository):
    """Repository for the ChapterVersions table."""

    def __init__(self, client: FeishuClient, app_token: str, table_id: str) -> None:
        from app.feishu.table_map import FIELD_MAPS

        super().__init__(client, app_token, table_id, FIELD_MAPS["chapter_versions"])

    # ----------------------------------------------------------
    # domain queries
    # ----------------------------------------------------------

    def find_by_chapter(self, book_id: str, chapter_no: int) -> list[dict]:
        """Return versions for a specific chapter of a book."""
        return self.list(
            filter_expr=(
                f'CurrentValue.[book_id] = "{book_id}"'
                f' && CurrentValue.[chapter_no] = {chapter_no}'
            )
        )
