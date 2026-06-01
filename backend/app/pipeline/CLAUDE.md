# app/pipeline/
> L2 | 父级: ../../CLAUDE.md

成员清单
__init__.py: 包入口，重导出 PipelineEngine、WorkerLoop、StepDef、PipelineDef。
models.py: StepDef 与 PipelineDef 冻结数据类，定义步骤依赖图结构。
engine.py: PipelineEngine 核心编排器，管理 PipelineRun/StepRun 生命周期与依赖解析。
worker.py: WorkerLoop lease-based step claiming 与执行循环，跨 worker 防重复执行。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
