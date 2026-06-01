"""
WorkerLoop 单元测试 — 使用 mock PipelineEngine 隔离 repo 层。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.pipeline.worker import WorkerLoop


# ============================================================
# fixtures
# ============================================================


@pytest.fixture()
def engine() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def worker(engine: MagicMock) -> WorkerLoop:
    return WorkerLoop(engine, worker_id="worker-1", lease_duration=300, max_retries=3)


# ============================================================
# claim_step
# ============================================================


class TestClaimStep:
    def test_sets_lease_owner_and_until(
        self, worker: WorkerLoop, engine: MagicMock
    ):
        engine._step_repo.update.return_value = {
            "step_run_id": "SR-001",
            "status": "running",
            "lease_owner": "worker-1",
        }

        result = worker.claim_step("SR-001")

        update_call = engine._step_repo.update.call_args[0]
        assert update_call[0] == "SR-001"
        assert update_call[1]["status"] == "running"
        assert update_call[1]["lease_owner"] == "worker-1"
        assert "lease_until" in update_call[1]


# ============================================================
# is_lease_expired
# ============================================================


class TestIsLeaseExpired:
    def test_returns_true_for_past_deadline(self, worker: WorkerLoop):
        past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        assert worker.is_lease_expired({"lease_until": past}) is True

    def test_returns_false_for_future_deadline(self, worker: WorkerLoop):
        future = (datetime.now(timezone.utc) + timedelta(seconds=300)).isoformat()
        assert worker.is_lease_expired({"lease_until": future}) is False

    def test_returns_true_for_empty_lease(self, worker: WorkerLoop):
        assert worker.is_lease_expired({"lease_until": ""}) is True
        assert worker.is_lease_expired({}) is True


# ============================================================
# poll_once
# ============================================================


class TestPollOnce:
    def test_claims_first_runnable_step(
        self, worker: WorkerLoop, engine: MagicMock
    ):
        engine._pipeline_repo.find_by_status.return_value = [
            {"pipeline_run_id": "PR-001", "status": "running"},
        ]
        engine.get_runnable_steps.return_value = [
            {"step_run_id": "SR-001", "step_key": "s1"},
        ]
        engine._step_repo.update.return_value = {
            "step_run_id": "SR-001",
            "status": "running",
            "lease_owner": "worker-1",
        }

        result = worker.poll_once()

        assert result is not None
        assert result["step_run_id"] == "SR-001"

    def test_returns_none_when_nothing_claimable(
        self, worker: WorkerLoop, engine: MagicMock
    ):
        engine._pipeline_repo.find_by_status.return_value = []
        assert worker.poll_once() is None

    def test_recovers_stale_lease(self, worker: WorkerLoop, engine: MagicMock):
        past = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()

        engine._pipeline_repo.find_by_status.side_effect = [
            [{"pipeline_run_id": "PR-001", "status": "running"}],
            [],
        ]
        engine.get_runnable_steps.return_value = []
        engine._step_repo.find_by_pipeline.return_value = [
            {"step_run_id": "SR-001", "status": "running", "lease_until": past},
        ]
        engine._step_repo.update.return_value = {
            "step_run_id": "SR-001",
            "status": "running",
            "lease_owner": "worker-1",
        }

        result = worker.poll_once()

        assert result is not None
        assert result["step_run_id"] == "SR-001"


# ============================================================
# execute_step
# ============================================================


class TestExecuteStep:
    def test_completes_on_success(self, worker: WorkerLoop, engine: MagicMock):
        handler = MagicMock(return_value={"output_refs": ["ref-1"]})
        engine.complete_step.return_value = {
            "step_run_id": "SR-001",
            "status": "success",
        }

        result = worker.execute_step("SR-001", handler)

        handler.assert_called_once_with("SR-001")
        engine.complete_step.assert_called_once_with("SR-001", ["ref-1"])
        assert result["status"] == "success"

    def test_fails_on_handler_exception(
        self, worker: WorkerLoop, engine: MagicMock
    ):
        handler = MagicMock(side_effect=ValueError("bad input"))
        engine._step_repo.get.return_value = {"retry_count": 0}
        engine.fail_step.return_value = {
            "step_run_id": "SR-001",
            "status": "failed",
        }

        result = worker.execute_step("SR-001", handler)

        engine.fail_step.assert_called_once()
        error_msg = engine.fail_step.call_args[0][1]
        assert "ValueError" in error_msg

    def test_requeues_when_retry_count_below_max(
        self, worker: WorkerLoop, engine: MagicMock
    ):
        handler = MagicMock(side_effect=RuntimeError("oops"))
        engine._step_repo.get.return_value = {"retry_count": 1}
        engine.fail_step.return_value = {"status": "failed"}

        worker.execute_step("SR-001", handler)

        requeue_call = engine._step_repo.update.call_args_list[-1]
        assert requeue_call[0][1]["status"] == "pending"
        assert requeue_call[0][1]["lease_owner"] == ""

    def test_does_not_requeue_at_max_retries(
        self, worker: WorkerLoop, engine: MagicMock
    ):
        handler = MagicMock(side_effect=RuntimeError("oops"))
        engine._step_repo.get.return_value = {"retry_count": 3}
        engine.fail_step.return_value = {"status": "failed"}

        worker.execute_step("SR-001", handler)

        update_calls = engine._step_repo.update.call_args_list
        statuses = [c[0][1].get("status") for c in update_calls]
        assert "pending" not in statuses

    def test_passes_none_output_refs_when_handler_returns_none(
        self, worker: WorkerLoop, engine: MagicMock
    ):
        handler = MagicMock(return_value=None)
        engine.complete_step.return_value = {"status": "success"}

        worker.execute_step("SR-001", handler)

        engine.complete_step.assert_called_once_with("SR-001", None)
