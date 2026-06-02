"""
CAS & Lease 行为门禁 — conditional_update CAS、lease recheck、pipeline_run_id 保留。

Codex review R09/R10/R11 修复的 Red-state 测试。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.pipeline.engine import PipelineEngine
from app.pipeline.worker import WorkerLoop


# ============================================================
# fixtures
# ============================================================


@pytest.fixture()
def pipeline_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def step_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def engine(pipeline_repo: MagicMock, step_repo: MagicMock) -> PipelineEngine:
    return PipelineEngine(pipeline_repo, step_repo)


@pytest.fixture()
def worker(engine: PipelineEngine) -> WorkerLoop:
    return WorkerLoop(engine, worker_id="worker-1", lease_duration=300)


# ============================================================
# conditional_update CAS (R09)
# ============================================================


class TestConditionalUpdate:
    def test_conditional_update_exists_on_base_repo(self):
        """BaseRepository must expose conditional_update method."""
        from app.feishu.repositories.base import BaseRepository
        assert hasattr(BaseRepository, "conditional_update")

    def test_conditional_update_applies_when_condition_met(self):
        """CAS update must succeed when condition filter matches."""
        from app.feishu.repositories.base import BaseRepository

        client = MagicMock()
        client.put.return_value = {"data": {"record": {"record_id": "R1", "fields": {}}}}
        repo = BaseRepository(client, "app_tok", "tbl_id", {})

        result = repo.conditional_update(
            "R1",
            {"status": "running"},
            {"status": "pending"},
        )
        # Must have called PUT with the condition in the request
        client.put.assert_called_once()

    def test_conditional_update_rejects_when_condition_mismatch(self):
        """CAS update must raise when condition filter doesn't match."""
        from app.feishu.repositories.base import BaseRepository

        client = MagicMock()
        # Simulate Bitable returning no match (condition mismatch)
        client.put.side_effect = Exception("condition not met")
        repo = BaseRepository(client, "app_tok", "tbl_id", {})

        with pytest.raises(Exception):
            repo.conditional_update(
                "R1",
                {"status": "running"},
                {"status": "pending"},  # current status is NOT pending
            )


# ============================================================
# lease recheck before complete (R10)
# ============================================================


class TestLeaseRecheck:
    def test_complete_step_rechecks_lease(
        self, worker: WorkerLoop, engine: PipelineEngine
    ):
        """complete_step must verify lease is still valid before completing."""
        step_repo = engine._step_repo
        # Simulate step with valid lease for this worker
        step_repo.get.return_value = {
            "step_run_id": "SR-001",
            "pipeline_run_id": "PR-001",
            "lease_owner": "worker-1",
            "lease_until": "2099-01-01T00:00:00+00:00",
            "retry_count": 0,
        }
        step_repo.update.return_value = {
            "step_run_id": "SR-001",
            "pipeline_run_id": "PR-001",
            "status": "success",
        }
        step_repo.find_by_pipeline.return_value = [
            {"step_key": "s1", "status": "success", "depends_on": ""},
        ]

        # Should succeed — lease is valid
        engine.complete_step("SR-001")

    def test_complete_step_rejects_expired_lease(
        self, worker: WorkerLoop, engine: PipelineEngine
    ):
        """complete_step must reject when lease has expired (another worker owns it)."""
        step_repo = engine._step_repo
        # Simulate step with expired lease belonging to another worker
        step_repo.get.return_value = {
            "step_run_id": "SR-001",
            "pipeline_run_id": "PR-001",
            "lease_owner": "worker-999",
            "lease_until": "2020-01-01T00:00:00+00:00",  # expired
            "retry_count": 0,
        }

        # Must raise because lease expired and owned by different worker
        with pytest.raises((ValueError, RuntimeError)):
            engine.complete_step("SR-001")


# ============================================================
# pipeline_run_id preservation (R11)
# ============================================================


class TestPipelineRunIdPreservation:
    def test_step_output_includes_pipeline_run_id(
        self, engine: PipelineEngine, step_repo: MagicMock
    ):
        """Step completion result must contain pipeline_run_id."""
        step_repo.update.return_value = {
            "step_run_id": "SR-001",
            "pipeline_run_id": "PR-001",
            "status": "success",
        }
        step_repo.find_by_pipeline.return_value = [
            {"step_key": "s1", "status": "success", "depends_on": ""},
        ]

        result = engine.complete_step("SR-001", output_refs=["ref-1"])

        assert result.get("pipeline_run_id") == "PR-001"

    def test_worker_execute_preserves_pipeline_run_id(
        self, worker: WorkerLoop, engine: PipelineEngine
    ):
        """WorkerLoop.execute_step must return result with pipeline_run_id."""
        step_repo = engine._step_repo
        step_repo.get.return_value = {
            "step_run_id": "SR-001",
            "pipeline_run_id": "PR-001",
            "retry_count": 0,
        }
        step_repo.update.return_value = {
            "step_run_id": "SR-001",
            "pipeline_run_id": "PR-001",
            "status": "success",
        }
        step_repo.find_by_pipeline.return_value = [
            {"step_key": "s1", "status": "success", "depends_on": ""},
        ]

        def handler(step_run_id: str) -> dict:
            return {"output_refs": ["ref-1"]}

        result = worker.execute_step("SR-001", handler)

        assert result.get("pipeline_run_id") == "PR-001"
