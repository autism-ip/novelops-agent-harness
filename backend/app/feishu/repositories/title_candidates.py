"""
[INPUT]: 依赖 app.feishu.repositories.base.BaseRepository 的 CRUD 能力
[OUTPUT]: 对外提供 TitleCandidatesRepo 类
[POS]: repositories 包的具体实现，封装 TitleCandidates 表的 CRUD 与领域查询
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository


# ============================================================
# title candidates repository
# ============================================================


class TitleCandidatesRepo(BaseRepository):
    """Repository for the TitleCandidates table."""

    def __init__(self, client: FeishuClient, app_token: str, table_id: str) -> None:
        from app.feishu.table_map import FIELD_MAPS

        super().__init__(client, app_token, table_id, FIELD_MAPS["title_candidates"])

    # ----------------------------------------------------------
    # domain queries
    # ----------------------------------------------------------

    def find_by_analysis(self, analysis_id: str) -> list[dict]:
        """Return title candidates for a specific analysis."""
        return self.list(filter_expr=self._field_filter(analysis_id=analysis_id))
