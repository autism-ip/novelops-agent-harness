"""
PipelineEngine 验证门禁 — 空步骤拒绝、depends_on 校验、环依赖检测。

Codex review R15/R16 修复的 Red-state 测试。
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
# empty steps rejection (R15)
# ============================================================


class TestEmptyStepsRejection:
    def test_rejects_empty_step_defs(
        self, engine: PipelineEngine
    ):
        """create_pipeline must raise ValueError on empty step_defs."""
        with pytest.raises(ValueError, match="step_defs"):
            engine.create_pipeline("test_type", [])

    def test_rejects_none_step_defs(
        self, engine: PipelineEngine
    ):
        """create_pipeline must raise ValueError on None step_defs."""
        with pytest.raises(ValueError, match="step_defs"):
            engine.create_pipeline("test_type", None)  # type: ignore[arg-type]


# ============================================================
# depends_on validation (R16)
# ============================================================


class TestDependsOnValidation:
    def test_rejects_unknown_depends_on(
        self, engine: PipelineEngine
    ):
        """Step referencing non-existent step_key must raise ValueError."""
        step_defs = [
            StepDef("s1", "agent-a"),
            StepDef("s2", "agent-b", depends_on=("nonexistent",)),
        ]
        with pytest.raises(ValueError, match="nonexistent"):
            engine.create_pipeline("test_type", step_defs)

    def test_accepts_valid_depends_on(
        self, engine: PipelineEngine, pipeline_repo: MagicMock
    ):
        """Valid depends_on references must be accepted."""
        step_defs = [
            StepDef("s1", "agent-a"),
            StepDef("s2", "agent-b", depends_on=("s1",)),
        ]
        engine.create_pipeline("test_type", step_defs)
        pipeline_repo.create.assert_called_once()


# ============================================================
# cyclic dependency detection (R16)
# ============================================================


class TestCyclicDependencyDetection:
    def test_detects_direct_cycle(
        self, engine: PipelineEngine
    ):
        """A → B → A cycle must raise ValueError."""
        step_defs = [
            StepDef("a", "agent-a", depends_on=("b",)),
            StepDef("b", "agent-b", depends_on=("a",)),
        ]
        with pytest.raises(ValueError, match="[Cc]ycl"):
            engine.create_pipeline("test_type", step_defs)

    def test_detects_indirect_cycle(
        self, engine: PipelineEngine
    ):
        """A → B → C → A cycle must raise ValueError."""
        step_defs = [
            StepDef("a", "agent-a", depends_on=("c",)),
            StepDef("b", "agent-b", depends_on=("a",)),
            StepDef("c", "agent-c", depends_on=("b",)),
        ]
        with pytest.raises(ValueError, match="[Cc]ycl"):
            engine.create_pipeline("test_type", step_defs)

    def test_accepts_dag(
        self, engine: PipelineEngine, pipeline_repo: MagicMock
    ):
        """Non-cyclic DAG must be accepted."""
        step_defs = [
            StepDef("a", "agent-a"),
            StepDef("b", "agent-b", depends_on=("a",)),
            StepDef("c", "agent-c", depends_on=("a",)),
            StepDef("d", "agent-d", depends_on=("b", "c")),
        ]
        engine.create_pipeline("test_type", step_defs)
        pipeline_repo.create.assert_called_once()
