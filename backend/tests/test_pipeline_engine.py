"""
PipelineEngine 单元测试 — 使用 mock repo 隔离飞书 Bitable 依赖。
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
# create_pipeline
# ============================================================


class TestCreatePipeline:
    def test_creates_pipeline_run_with_pending_status(
        self, engine: PipelineEngine, pipeline_repo: MagicMock
    ):
        step_defs = [
            StepDef("extract", "agent-a"),
            StepDef("analyze", "agent-b", depends_on=("extract",)),
        ]

        result = engine.create_pipeline("douyin_to_novel", step_defs)

        pipeline_repo.create.assert_called_once()
        created = pipeline_repo.create.call_args[0][0]
        assert created["pipeline_type"] == "douyin_to_novel"
        assert created["status"] == "pending"
        assert created["current_step"] == "extract"
        assert created["pipeline_run_id"].startswith("PR-")

    def test_creates_step_runs_for_each_def(
        self, engine: PipelineEngine, step_repo: MagicMock
    ):
        step_defs = [
            StepDef("s1", "a1"),
            StepDef("s2", "a2", depends_on=("s1",)),
            StepDef("s3", "a3", depends_on=("s1",)),
        ]

        engine.create_pipeline("test_type", step_defs)

        assert step_repo.create.call_count == 3
        calls = step_repo.create.call_args_list
        keys = [c[0][0]["step_key"] for c in calls]
        assert keys == ["s1", "s2", "s3"]
        assert calls[1][0][0]["depends_on"] == "s1"
        assert calls[2][0][0]["depends_on"] == "s1"

    def test_passes_source_hotspot_and_book_id(
        self, engine: PipelineEngine, pipeline_repo: MagicMock
    ):
        engine.create_pipeline(
            "t",
            [StepDef("x", "a")],
            source_hotspot_id="HS-001",
            book_id="BK-001",
            operator="zen",
        )
        created = pipeline_repo.create.call_args[0][0]
        assert created["source_hotspot_id"] == "HS-001"
        assert created["book_id"] == "BK-001"
        assert created["operator"] == "zen"


# ============================================================
# get_runnable_steps
# ============================================================


class TestGetRunnableSteps:
    def test_returns_pending_steps_with_met_deps(
        self, engine: PipelineEngine, step_repo: MagicMock
    ):
        step_repo.find_by_pipeline.return_value = [
            {"step_key": "s1", "status": "success", "depends_on": ""},
            {"step_key": "s2", "status": "pending", "depends_on": "s1"},
            {"step_key": "s3", "status": "pending", "depends_on": "s1,s2"},
        ]

        runnable = engine.get_runnable_steps("PR-001")

        keys = [s["step_key"] for s in runnable]
        assert "s2" in keys
        assert "s3" not in keys

    def test_returns_empty_when_no_pending(
        self, engine: PipelineEngine, step_repo: MagicMock
    ):
        step_repo.find_by_pipeline.return_value = [
            {"step_key": "s1", "status": "success", "depends_on": ""},
        ]
        assert engine.get_runnable_steps("PR-001") == []

    def test_handles_empty_depends_on(
        self, engine: PipelineEngine, step_repo: MagicMock
    ):
        step_repo.find_by_pipeline.return_value = [
            {"step_key": "s1", "status": "pending", "depends_on": ""},
        ]
        runnable = engine.get_runnable_steps("PR-001")
        assert len(runnable) == 1


# ============================================================
# complete_step
# ============================================================


class TestCompleteStep:
    def test_marks_step_as_success(
        self, engine: PipelineEngine, step_repo: MagicMock
    ):
        step_repo.update.return_value = {
            "step_run_id": "SR-001",
            "pipeline_run_id": "PR-001",
            "status": "success",
        }
        step_repo.find_by_pipeline.return_value = [
            {"step_key": "s1", "status": "success", "depends_on": ""},
        ]

        engine.complete_step("SR-001", output_refs=["ref-1"])

        update_call = step_repo.update.call_args[0]
        assert update_call[0] == "SR-001"
        assert update_call[1]["status"] == "success"
        assert update_call[1]["output_refs"] == "ref-1"

    def test_advances_pipeline_when_runnable_steps_exist(
        self, engine: PipelineEngine, step_repo: MagicMock, pipeline_repo: MagicMock
    ):
        step_repo.update.return_value = {
            "step_run_id": "SR-001",
            "pipeline_run_id": "PR-001",
        }
        step_repo.find_by_pipeline.return_value = [
            {"step_key": "s1", "status": "success", "depends_on": ""},
            {"step_key": "s2", "status": "pending", "depends_on": "s1"},
        ]

        engine.complete_step("SR-001")

        pipeline_repo.update.assert_called_once()
        update_data = pipeline_repo.update.call_args[0][1]
        assert update_data["current_step"] == "s2"
        assert update_data["status"] == "running"

    def test_completes_pipeline_when_all_steps_success(
        self, engine: PipelineEngine, step_repo: MagicMock, pipeline_repo: MagicMock
    ):
        step_repo.update.return_value = {
            "step_run_id": "SR-002",
            "pipeline_run_id": "PR-001",
        }
        step_repo.find_by_pipeline.return_value = [
            {"step_key": "s1", "status": "success", "depends_on": ""},
            {"step_key": "s2", "status": "success", "depends_on": "s1"},
        ]

        engine.complete_step("SR-002")

        pipeline_repo.update.assert_called_once()
        update_data = pipeline_repo.update.call_args[0][1]
        assert update_data["status"] == "completed"


# ============================================================
# fail_step
# ============================================================


class TestFailStep:
    def test_marks_step_as_failed_and_increments_retry(
        self, engine: PipelineEngine, step_repo: MagicMock
    ):
        step_repo.get.return_value = {"retry_count": 1}
        step_repo.update.return_value = {"status": "failed", "retry_count": 2}

        engine.fail_step("SR-001", "ValueError: bad input")

        update_call = step_repo.update.call_args[0]
        assert update_call[1]["status"] == "failed"
        assert update_call[1]["retry_count"] == 2
        assert "ValueError" in update_call[1]["error_message"]

    def test_defaults_retry_count_to_zero(
        self, engine: PipelineEngine, step_repo: MagicMock
    ):
        step_repo.get.return_value = None

        engine.fail_step("SR-001", "error")

        update_call = step_repo.update.call_args[0]
        assert update_call[1]["retry_count"] == 1


# ============================================================
# rollback
# ============================================================


class TestRollback:
    def test_rollback_deletes_by_feishu_record_id(
        self,
        engine: PipelineEngine,
        pipeline_repo: MagicMock,
        step_repo: MagicMock,
    ):
        """When step creation fails mid-way, rollback deletes by record_id."""
        step_defs = [
            StepDef("s1", "a1"),
            StepDef("s2", "a2", depends_on=("s1",)),
        ]

        # First create succeeds, returning a record_id from Feishu
        step_repo.create.side_effect = [
            {"step_run_id": "SR-001", "record_id": "rec_abc123"},
            RuntimeError("Feishu write failed"),
        ]

        with pytest.raises(RuntimeError, match="Feishu write failed"):
            engine.create_pipeline("test_type", step_defs)

        # Rollback must delete by record_id, not by step_run_id
        step_repo.delete.assert_called_once_with("rec_abc123")
        pipeline_repo.delete.assert_called_once()

    def test_rollback_falls_back_to_step_run_id_when_no_record_id(
        self,
        engine: PipelineEngine,
        pipeline_repo: MagicMock,
        step_repo: MagicMock,
    ):
        """If record_id is missing from result, fallback to step_run_id."""
        step_defs = [
            StepDef("s1", "a1"),
            StepDef("s2", "a2", depends_on=("s1",)),
        ]

        step_repo.create.side_effect = [
            {"step_run_id": "SR-001"},  # no record_id key
            RuntimeError("boom"),
        ]

        with pytest.raises(RuntimeError):
            engine.create_pipeline("test_type", step_defs)

        step_repo.delete.assert_called_once_with("SR-001")


# ============================================================
# validation
# ============================================================


class TestValidation:
    def test_duplicate_step_key_rejected_with_name(
        self, engine: PipelineEngine
    ):
        step_defs = [
            StepDef("extract", "agent-a"),
            StepDef("extract", "agent-b"),  # duplicate
        ]
        with pytest.raises(ValueError, match="Duplicate step_key.*'extract'"):
            engine.create_pipeline("test_type", step_defs)

    def test_unknown_dependency_rejected(
        self, engine: PipelineEngine
    ):
        step_defs = [
            StepDef("s1", "a1", depends_on=("ghost",)),
        ]
        with pytest.raises(ValueError, match="unknown step 'ghost'"):
            engine.create_pipeline("test_type", step_defs)
