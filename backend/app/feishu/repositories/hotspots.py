"""
[INPUT]: 依赖 app.feishu.repositories.base.BaseRepository 的 CRUD 能力
[OUTPUT]: 对外提供 HotspotsRepo 类
[POS]: repositories 包的具体实现，封装 Hotspots 表的 CRUD 与领域查询
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository


# ============================================================
# hotspots repository
# ============================================================


class HotspotsRepo(BaseRepository):
    """Repository for the Hotspots table."""

    def __init__(self, client: FeishuClient, app_token: str, table_id: str) -> None:
        from app.feishu.table_map import FIELD_MAPS

        super().__init__(client, app_token, table_id, FIELD_MAPS["hotspots"])

    # ----------------------------------------------------------
    # domain queries
    # ----------------------------------------------------------

    def find_by_status(self, status: str) -> list[dict]:
        """Return hotspots matching *status*."""
        return self.list(filter_expr=f'CurrentValue.[status] = "{status}"')

    def find_by_dedupe_hash(self, dedupe_hash: str) -> list[dict]:
        """Return hotspots matching *dedupe_hash* (deduplication check)."""
        return self.list(
            filter_expr=f'CurrentValue.[dedupe_hash] = "{dedupe_hash}"'
        )
