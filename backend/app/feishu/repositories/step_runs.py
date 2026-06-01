"""
[INPUT]: 依赖 app.feishu.repositories.base.BaseRepository 的 CRUD 能力
[OUTPUT]: 对外提供 StepRunsRepo 类
[POS]: repositories 包的具体实现，封装 StepRuns 表的 CRUD 与领域查询
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository


# ============================================================
# step runs repository
# ============================================================


class StepRunsRepo(BaseRepository):
    """Repository for the StepRuns table."""

    def __init__(self, client: FeishuClient, app_token: str, table_id: str) -> None:
        from app.feishu.table_map import FIELD_MAPS

        super().__init__(client, app_token, table_id, FIELD_MAPS["step_runs"])

    # ----------------------------------------------------------
    # domain queries
    # ----------------------------------------------------------

    def find_by_pipeline(self, pipeline_run_id: str) -> list[dict]:
        """Return step runs belonging to a specific pipeline run."""
        return self.list(
            filter_expr=self._field_filter(pipeline_run_id=pipeline_run_id)
        )

    def claim_step(self, step_run_id: str, owner: str) -> dict:
        """Claim a step by resolving business key to record_id, then updating."""
        record = self.find_by_business_key(step_run_id=step_run_id)
        if record is None:
            raise ValueError(f"Step run not found: {step_run_id}")
        return self.update(
            record["record_id"],
            {"lease_owner": owner, "status": "running"},
        )
