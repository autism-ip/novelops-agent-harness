"""
PipelineEngine 状态机门禁 — rollback、run_id 生成、failure cascade。

Codex review R12/R13/R14 修复的 Red-state 测试。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.pipeline.engine import PipelineEngine
from app.pipeline.models import StepDef


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


# ============================================================
# rollback on partial creation failure (R12)
# ============================================================


class TestRollbackOnPartialFailure:
    def test_cleans_up_pipeline_when_step_creation_fails(
        self, engine: PipelineEngine, pipeline_repo: MagicMock, step_repo: MagicMock
    ):
        """If step creation fails mid-way, pipeline record must be deleted."""
        step_defs = [
            StepDef("s1", "agent-a"),
            StepDef("s2", "agent-b", depends_on=("s1",)),
            StepDef("s3", "agent-c", depends_on=("s1",)),
        ]

        # First step creation succeeds, second raises
        step_repo.create.side_effect = [
            {"step_run_id": "SR-001"},  # s1 ok
            RuntimeError("feishu down"),  # s2 fails
        ]

        with pytest.raises(RuntimeError, match="feishu down"):
            engine.create_pipeline("test_type", step_defs)

        # Pipeline record must be cleaned up
        pipeline_repo.delete.assert_called_once()

    def test_cleans_up_created_steps_on_failure(
        self, engine: PipelineEngine, pipeline_repo: MagicMock, step_repo: MagicMock
    ):
        """Already-created step records must also be deleted on partial failure."""
        step_defs = [
            StepDef("s1", "agent-a"),
            StepDef("s2", "agent-b", depends_on=("s1",)),
        ]

        step_repo.create.side_effect = [
            {"step_run_id": "SR-001"},  # s1 ok
            RuntimeError("boom"),  # s2 fails
        ]

        with pytest.raises(RuntimeError):
            engine.create_pipeline("test_type", step_defs)

        # s1's step record must be cleaned up
        step_repo.delete.assert_called_with("SR-001")


# ============================================================
# run_id generation (R13)
# ============================================================


class TestRunIdGeneration:
    def test_pipeline_run_id_has_prefix(
        self, engine: PipelineEngine, pipeline_repo: MagicMock
    ):
        """pipeline_run_id must use PR- prefix."""
        engine.create_pipeline("t", [StepDef("s1", "a1")])
        created = pipeline_repo.create.call_args[0][0]
        assert created["pipeline_run_id"].startswith("PR-")

    def test_step_run_id_has_prefix(
        self, engine: PipelineEngine, step_repo: MagicMock
    ):
        """step_run_id must use SR- prefix."""
        engine.create_pipeline("t", [StepDef("s1", "a1")])
        created = step_repo.create.call_args[0][0]
        assert created["step_run_id"].startswith("SR-")

    def test_run_ids_are_unique(
        self, engine: PipelineEngine, pipeline_repo: MagicMock, step_repo: MagicMock
    ):
        """Multiple calls must produce unique run IDs."""
        engine.create_pipeline("t", [StepDef("s1", "a1")])
        pr_id_1 = pipeline_repo.create.call_args_list[0][0][0]["pipeline_run_id"]

        pipeline_repo.reset_mock()
        step_repo.reset_mock()

        engine.create_pipeline("t", [StepDef("s2", "a2")])
        pr_id_2 = pipeline_repo.create.call_args_list[0][0][0]["pipeline_run_id"]

        assert pr_id_1 != pr_id_2


# ============================================================
# failure cascade (R14)
# ============================================================


class TestFailureCascade:
    def test_pipeline_fails_when_all_retries_exhausted(
        self, engine: PipelineEngine, step_repo: MagicMock, pipeline_repo: MagicMock
    ):
        """When a step permanently fails (retries exhausted), pipeline must transition to failed."""
        step_repo.get.return_value = {
            "step_run_id": "SR-001",
            "pipeline_run_id": "PR-001",
            "retry_count": 3,  # max retries reached
        }
        step_repo.update.return_value = {
            "step_run_id": "SR-001",
            "pipeline_run_id": "PR-001",
            "status": "failed",
            "retry_count": 4,
        }

        engine.fail_step("SR-001", "permanent error")

        # Pipeline must be updated to failed status
        pipeline_repo.update.assert_called_once()
        update_data = pipeline_repo.update.call_args[0][1]
        assert update_data["status"] == "failed"

    def test_pipeline_not_failed_when_retries_remain(
        self, engine: PipelineEngine, step_repo: MagicMock, pipeline_repo: MagicMock
    ):
        """When retries remain, pipeline must NOT transition to failed."""
        step_repo.get.return_value = {
            "step_run_id": "SR-001",
            "pipeline_run_id": "PR-001",
            "retry_count": 1,  # retries remaining
        }
        step_repo.update.return_value = {
            "step_run_id": "SR-001",
            "pipeline_run_id": "PR-001",
            "status": "failed",
            "retry_count": 2,
        }

        engine.fail_step("SR-001", "transient error")

        # Pipeline must NOT be updated to failed
        pipeline_repo.update.assert_not_called()
