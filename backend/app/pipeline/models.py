"""
[INPUT]: 无外部依赖
[OUTPUT]: 对外提供 StepDef、PipelineDef 数据类
[POS]: pipeline 包的数据模型，定义步骤依赖图结构
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from dataclasses import dataclass


# ============================================================
# step definition
# ============================================================


@dataclass(frozen=True)
class StepDef:
    """Immutable definition of a single pipeline step."""

    step_key: str
    assigned_agent_id: str
    depends_on: tuple[str, ...] = ()


# ============================================================
# pipeline definition
# ============================================================


@dataclass(frozen=True)
class PipelineDef:
    """Immutable definition of a pipeline type and its steps."""

    pipeline_type: str
    steps: tuple[StepDef, ...] = ()
