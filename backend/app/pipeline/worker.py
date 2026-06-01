"""
[INPUT]: 依赖 PipelineEngine 的 get_runnable_steps / complete_step / fail_step，
         依赖 PipelineRunsRepo 的 find_by_status，依赖 StepRunsRepo 的 update
[OUTPUT]: 对外提供 WorkerLoop 类——lease-based step claiming 与执行循环
[POS]: pipeline 包的执行引擎，被启动脚本或测试消费，编排 step 的 claim/execute/complete 生命周期
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import traceback
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.pipeline.engine import PipelineEngine


# ============================================================
# worker loop
# ============================================================


class WorkerLoop:
    """Poll-based worker that claims and executes pipeline steps.

    Uses lease-based claiming to prevent duplicate execution across
    multiple worker instances. Each claim sets a time-bounded lease;
    expired leases allow other workers to reclaim stalled steps.
    """

    def __init__(
        self,
        engine: PipelineEngine,
        worker_id: str,
        poll_interval: float = 5.0,
        lease_duration: int = 300,
        max_retries: int = 3,
    ) -> None:
        self._engine = engine
        self._worker_id = worker_id
        self._poll_interval = poll_interval
        self._lease_duration = lease_duration
        self._max_retries = max_retries

    # ----------------------------------------------------------
    # poll — find next claimable step
    # ----------------------------------------------------------

    def poll_once(self) -> dict | None:
        """Find next claimable step across all active pipelines.

        Claimability rules:
          1. status == "pending" with all dependencies satisfied
          2. status == "running" with expired lease (stale recovery)

        Returns the claimed step dict, or None if nothing available.
        """
        for status in ("running", "pending"):
            pipelines = self._engine._pipeline_repo.find_by_status(status)
            for pipeline in pipelines:
                pipeline_run_id = pipeline.get("pipeline_run_id", "")
                if not pipeline_run_id:
                    continue

                step = self._find_claimable_in_pipeline(pipeline_run_id)
                if step is not None:
                    return step

        return None

    # ----------------------------------------------------------
    # execute — run handler with success/fail routing
    # ----------------------------------------------------------

    def execute_step(
        self, step_run_id: str, handler: Callable[[str], dict | None]
    ) -> dict:
        """Run *handler(step_run_id)* and route to complete or fail.

        On success: engine.complete_step with optional output_refs.
        On exception: if retry_count < max_retries, re-queue to pending;
                      otherwise leave as permanently failed.
        """
        now = datetime.now(timezone.utc).isoformat()
        self._engine._step_repo.update(step_run_id, {"started_at": now})

        try:
            result = handler(step_run_id)

            # Recheck lease before completing (defense-in-depth)
            step = self._engine._step_repo.get(step_run_id)
            if step and self.is_lease_expired(step):
                raise RuntimeError(f"Lease expired for step {step_run_id} before complete")

            output_refs = result.get("output_refs") if result else None
            return self._engine.complete_step(step_run_id, output_refs)
        except Exception as exc:
            step = self._engine._step_repo.get(step_run_id)
            retry_count = step.get("retry_count", 0) if step else 0
            error_msg = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"

            if retry_count < self._max_retries:
                # re-queue: increment retry count, clear lease
                self._engine._step_repo.update(step_run_id, {
                    "status": "pending",
                    "lease_owner": "",
                    "lease_until": "",
                    "retry_count": retry_count + 1,
                    "error_message": error_msg,
                })
                return self._engine._step_repo.get(step_run_id) or {}

            # retries exhausted → permanent failure
            return self._engine.fail_step(step_run_id, error_msg)

    # ----------------------------------------------------------
    # claim — set lease and transition to running
    # ----------------------------------------------------------

    def claim_step(self, step_run_id: str) -> dict:
        """Claim a step with CAS: only if unowned or already ours."""
        step = self._engine._step_repo.get(step_run_id)
        if step is None:
            raise ValueError(f"Step not found: {step_run_id}")

        current_owner = step.get("lease_owner", "")
        if current_owner and current_owner != self._worker_id:
            if not self.is_lease_expired(step):
                raise RuntimeError(f"Step {step_run_id} owned by {current_owner}")

        now = datetime.now(timezone.utc)
        lease_until = (now + timedelta(seconds=self._lease_duration)).isoformat()

        result = self._engine._step_repo.update(step_run_id, {
            "status": "running",
            "lease_owner": self._worker_id,
            "lease_until": lease_until,
            "started_at": now.isoformat(),
        })

        # Transition pipeline to "running" on first claim
        pipeline_run_id = step.get("pipeline_run_id", "")
        if pipeline_run_id:
            pipeline = self._engine._pipeline_repo.get(pipeline_run_id)
            if pipeline and pipeline.get("status") == "pending":
                self._engine._pipeline_repo.update(pipeline_run_id, {
                    "status": "running",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })

        return result

    # ----------------------------------------------------------
    # lease check
    # ----------------------------------------------------------

    def is_lease_expired(self, step_run: dict) -> bool:
        """Return True if lease_until is in the past."""
        lease_until = step_run.get("lease_until", "")
        if not lease_until:
            return True
        try:
            deadline = datetime.fromisoformat(lease_until)
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) > deadline
        except (ValueError, TypeError):
            return True

    # ----------------------------------------------------------
    # internal helpers
    # ----------------------------------------------------------

    def _find_claimable_in_pipeline(self, pipeline_run_id: str) -> dict | None:
        """Find and claim the first claimable step in a single pipeline."""
        # path A: pending steps with satisfied dependencies
        runnable = self._engine.get_runnable_steps(pipeline_run_id)
        for step in runnable:
            step_run_id = step.get("step_run_id", "")
            if not step_run_id:
                continue
            try:
                return self.claim_step(step_run_id)
            except Exception:
                continue

        # path B: running steps with expired leases (stale recovery)
        all_steps = self._engine._step_repo.find_by_pipeline(pipeline_run_id)
        for step in all_steps:
            if step.get("status") != "running":
                continue
            if not self.is_lease_expired(step):
                continue
            step_run_id = step.get("step_run_id", "")
            if not step_run_id:
                continue
            try:
                return self.claim_step(step_run_id)
            except Exception:
                continue

        return None
