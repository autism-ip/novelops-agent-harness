"""
[INPUT]: 依赖 PipelineRunsRepo、StepRunsRepo 的 CRUD 能力，依赖 models.StepDef
[OUTPUT]: 对外提供 PipelineEngine 类
[POS]: pipeline 包的核心编排器，管理 PipelineRun/StepRun 生命周期与依赖解析
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.feishu.repositories.pipeline_runs import PipelineRunsRepo
from app.feishu.repositories.step_runs import StepRunsRepo
from app.pipeline.models import StepDef


# ============================================================
# pipeline engine
# ============================================================


class PipelineEngine:
    """Table-driven pipeline execution core.

    Creates PipelineRun + StepRuns, resolves runnable steps,
    and manages step completion / failure transitions.
    """

    def __init__(
        self,
        pipeline_repo: PipelineRunsRepo,
        step_repo: StepRunsRepo,
    ) -> None:
        self._pipeline_repo = pipeline_repo
        self._step_repo = step_repo

    # ----------------------------------------------------------
    # pipeline creation
    # ----------------------------------------------------------

    def create_pipeline(
        self,
        pipeline_type: str,
        step_defs: list[StepDef],
        source_hotspot_id: str = "",
        book_id: str = "",
        operator: str = "",
    ) -> dict:
        """Create a PipelineRun and all associated StepRuns."""
        pipeline_run_id = f"PR-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        first_step = step_defs[0].step_key if step_defs else ""

        pipeline = self._pipeline_repo.create({
            "pipeline_run_id": pipeline_run_id,
            "pipeline_type": pipeline_type,
            "status": "pending",
            "current_step": first_step,
            "source_hotspot_id": source_hotspot_id,
            "book_id": book_id,
            "operator": operator,
            "created_at": now,
            "updated_at": now,
        })

        for step_def in step_defs:
            self._step_repo.create({
                "step_run_id": f"SR-{uuid.uuid4().hex[:12]}",
                "pipeline_run_id": pipeline_run_id,
                "step_key": step_def.step_key,
                "assigned_agent_id": step_def.assigned_agent_id,
                "depends_on": ",".join(step_def.depends_on),
                "status": "pending",
                "retry_count": 0,
            })

        return pipeline

    # ----------------------------------------------------------
    # dependency resolution
    # ----------------------------------------------------------

    def get_runnable_steps(self, pipeline_run_id: str) -> list[dict]:
        """Return steps whose dependencies are all satisfied."""
        all_steps = self._step_repo.find_by_pipeline(pipeline_run_id)
        completed_keys = {
            s["step_key"] for s in all_steps if s.get("status") == "success"
        }

        runnable = []
        for step in all_steps:
            if step.get("status") != "pending":
                continue
            deps = _parse_depends_on(step.get("depends_on", ""))
            if deps.issubset(completed_keys):
                runnable.append(step)

        return runnable

    # ----------------------------------------------------------
    # step transitions
    # ----------------------------------------------------------

    def complete_step(
        self, step_run_id: str, output_refs: list[str] | None = None
    ) -> dict:
        """Mark a step as success and advance the pipeline."""
        update_data: dict = {"status": "success"}
        if output_refs:
            update_data["output_refs"] = ",".join(output_refs)

        step = self._step_repo.update(step_run_id, update_data)
        pipeline_run_id = step.get("pipeline_run_id", "")

        runnable = self.get_runnable_steps(pipeline_run_id)
        if runnable:
            self._pipeline_repo.update(pipeline_run_id, {
                "current_step": runnable[0]["step_key"],
                "status": "running",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        else:
            all_steps = self._step_repo.find_by_pipeline(pipeline_run_id)
            if all(s.get("status") == "success" for s in all_steps):
                self._pipeline_repo.update(pipeline_run_id, {
                    "status": "completed",
                    "current_step": "",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })

        return step

    def fail_step(self, step_run_id: str, error_message: str) -> dict:
        """Mark a step as failed."""
        step = self._step_repo.get(step_run_id)
        retry_count = step.get("retry_count", 0) if step else 0

        return self._step_repo.update(step_run_id, {
            "status": "failed",
            "error_message": error_message,
            "retry_count": retry_count + 1,
        })


# ============================================================
# helpers
# ============================================================


def _parse_depends_on(depends_on: str) -> set[str]:
    """Parse comma-separated depends_on string into a set."""
    if not depends_on:
        return set()
    return {d.strip() for d in depends_on.split(",") if d.strip()}
