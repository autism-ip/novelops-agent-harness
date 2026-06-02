"""
[INPUT]: 依赖 PipelineRunsRepo、StepRunsRepo 的 CRUD 能力，依赖 models.StepDef
[OUTPUT]: 对外提供 PipelineEngine 类（含 validation、rollback by record_id、failure cascade）
[POS]: pipeline 包的核心编排器，管理 PipelineRun/StepRun 生命周期、依赖解析与状态转换
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
        max_retries: int = 3,
    ) -> None:
        self._pipeline_repo = pipeline_repo
        self._step_repo = step_repo
        self._max_retries = max_retries

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
        if not step_defs:
            raise ValueError("step_defs must not be empty")

        _validate_step_defs(step_defs)
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

        created_step_ids: list[str] = []
        try:
            for step_def in step_defs:
                result = self._step_repo.create({
                    "step_run_id": f"SR-{uuid.uuid4().hex[:12]}",
                    "pipeline_run_id": pipeline_run_id,
                    "step_key": step_def.step_key,
                    "assigned_agent_id": step_def.assigned_agent_id,
                    "depends_on": ",".join(step_def.depends_on),
                    "status": "pending",
                    "retry_count": 0,
                })
                created_step_ids.append(result.get("record_id", result.get("step_run_id", "")))
        except Exception:
            # rollback: delete created steps, then pipeline
            for sid in created_step_ids:
                try:
                    self._step_repo.delete(sid)
                except Exception:
                    pass
            try:
                self._pipeline_repo.delete(pipeline_run_id)
            except Exception:
                pass
            raise

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
    # record_id resolution
    # ----------------------------------------------------------

    def _resolve_step_record_id(self, step_run_id: str) -> str:
        """Resolve business key to Feishu record_id via find_by_business_key."""
        record = self._step_repo.find_by_business_key(step_run_id=step_run_id)
        if record is None:
            raise ValueError(f"Step run not found: {step_run_id}")
        return record["record_id"]

    # ----------------------------------------------------------
    # step transitions
    # ----------------------------------------------------------

    def complete_step(
        self, step_run_id: str, output_refs: list[str] | None = None
    ) -> dict:
        """Mark a step as success and advance the pipeline.

        Rechecks lease validity before completing — rejects if the
        lease has expired (another worker may have reclaimed the step).
        """
        record_id = self._resolve_step_record_id(step_run_id)
        step = self._step_repo.get(record_id)
        pipeline_run_id = step.get("pipeline_run_id", "") if step else ""

        if step:
            lease_until = step.get("lease_until", "")
            if lease_until:
                from datetime import datetime as _dt
                try:
                    deadline = _dt.fromisoformat(lease_until)
                    if deadline.tzinfo is None:
                        deadline = deadline.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) > deadline:
                        raise RuntimeError(
                            f"Lease expired for step {step_run_id}"
                        )
                except (ValueError, TypeError):
                    pass

        update_data: dict = {"status": "success"}
        if output_refs:
            update_data["output_refs"] = ",".join(output_refs)

        step = self._step_repo.update(record_id, update_data)

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
        """Mark a step as failed.

        When retries are exhausted (retry_count >= max_retries), cascades failure
        to the parent pipeline.
        """
        record_id = self._resolve_step_record_id(step_run_id)
        step = self._step_repo.get(record_id)
        retry_count = step.get("retry_count", 0) if step else 0

        result = self._step_repo.update(record_id, {
            "status": "failed",
            "error_message": error_message,
            "retry_count": retry_count + 1,
        })

        # Cascade: when retries exhausted, fail the pipeline
        if retry_count >= self._max_retries:
            pipeline_run_id = result.get("pipeline_run_id", "")
            if pipeline_run_id:
                self._pipeline_repo.update(pipeline_run_id, {
                    "status": "failed",
                    "error_message": error_message,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })

        return result


# ============================================================
# helpers
# ============================================================


def _parse_depends_on(depends_on: str) -> set[str]:
    """Parse comma-separated depends_on string into a set."""
    if not depends_on:
        return set()
    return {d.strip() for d in depends_on.split(",") if d.strip()}


def _validate_step_defs(step_defs: list[StepDef]) -> None:
    """Validate step definitions: depends_on references and cycle detection."""
    all_keys = {s.step_key for s in step_defs}
    if len(all_keys) != len(step_defs):
        seen: set[str] = set()
        for s in step_defs:
            if s.step_key in seen:
                raise ValueError(f"Duplicate step_key detected: '{s.step_key}'")
            seen.add(s.step_key)

    # Check depends_on references exist
    for step in step_defs:
        for dep in step.depends_on:
            if dep not in all_keys:
                raise ValueError(
                    f"Step '{step.step_key}' depends on unknown step '{dep}'"
                )

    # Check for cycles using Kahn's algorithm
    if _has_cycle(step_defs):
        raise ValueError("Cyclic dependency detected in step definitions")


def _has_cycle(step_defs: list[StepDef]) -> bool:
    """Return True if the step dependency graph contains a cycle."""
    # Build adjacency list and in-degree map
    in_degree: dict[str, int] = {s.step_key: 0 for s in step_defs}
    adj: dict[str, list[str]] = {s.step_key: [] for s in step_defs}

    for step in step_defs:
        for dep in step.depends_on:
            adj[dep].append(step.step_key)
            in_degree[step.step_key] += 1

    # Kahn's algorithm
    queue = [k for k, d in in_degree.items() if d == 0]
    visited = 0

    while queue:
        node = queue.pop(0)
        visited += 1
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return visited != len(step_defs)
