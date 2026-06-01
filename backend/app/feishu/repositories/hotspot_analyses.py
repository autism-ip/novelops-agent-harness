"""
[INPUT]: 依赖 app.feishu.repositories.base.BaseRepository 的 CRUD 能力
[OUTPUT]: 对外提供 HotspotAnalysesRepo 类
[POS]: repositories 包的具体实现，封装 HotspotAnalyses 表的 CRUD 与领域查询
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository


# ============================================================
# hotspot analyses repository
# ============================================================


class HotspotAnalysesRepo(BaseRepository):
    """Repository for the HotspotAnalyses table."""

    def __init__(self, client: FeishuClient, app_token: str, table_id: str) -> None:
        from app.feishu.table_map import FIELD_MAPS

        super().__init__(client, app_token, table_id, FIELD_MAPS["hotspot_analyses"])

    # ----------------------------------------------------------
    # domain queries
    # ----------------------------------------------------------

    def find_by_hotspot(self, hotspot_id: str) -> list[dict]:
        """Return analyses for a specific hotspot."""
        return self.list(filter_expr=f'CurrentValue.[hotspot_id] = "{hotspot_id}"')
