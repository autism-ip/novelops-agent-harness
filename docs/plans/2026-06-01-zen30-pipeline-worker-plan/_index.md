# ZEN-30: Build PipelineRun, StepRun, and worker loop primitives

## Context

ZEN-29 delivered the repository layer (16 repos over Feishu Bitable). ZEN-30 builds the execution core on top: a PipelineEngine service that manages PipelineRun/StepRun lifecycles, a lease-based step claiming mechanism, and a WorkerLoop that polls for runnable steps and executes them.

The 22-step `douyin_to_novel_chapter` pipeline (defined in `docs/pipeline-v0.1.md`) needs a table-driven executor. Each step has dependencies (`depends_on`), an assigned agent, and status transitions. The worker loop must be idempotent and lease-safe to support concurrent workers.

## Architecture

```
backend/app/pipeline/
├── __init__.py
├── CLAUDE.md
├── engine.py          # PipelineEngine — create pipelines, create steps, resolve dependencies
├── worker.py          # WorkerLoop — poll, claim, execute, complete/fail
└── models.py          # StepDef, PipelineDef — step dependency graph definitions

backend/app/api/routes/
└── pipelines.py       # API endpoints for pipeline CRUD and observation
```

## Current State vs Target State

| Dimension | Current | Target |
|-----------|---------|--------|
| Pipeline execution | No pipeline logic exists | PipelineEngine creates PipelineRun + StepRuns |
| Step claiming | `StepRunsRepo.claim_step()` is a simple update | Lease-aware claiming with `lease_until` expiry |
| Worker loop | Does not exist | Polling loop that claims next runnable step |
| Retry handling | No retry logic | Failed steps with `retry_count < max` re-queued |
| API observation | No pipeline endpoints | REST endpoints for pipeline/step state |

## Execution Plan

```yaml
tasks:
  - id: "001"
    subject: "Create pipeline models and engine service"
    slug: "create-pipeline-engine"
    type: "impl"
    depends-on: []
  - id: "002"
    subject: "Create worker loop with lease-based claiming"
    slug: "create-worker-loop"
    type: "impl"
    depends-on: ["001"]
  - id: "003"
    subject: "Create pipeline API endpoints"
    slug: "create-pipeline-api"
    type: "impl"
    depends-on: ["001"]
  - id: "004"
    subject: "Write unit tests for engine and worker"
    slug: "write-pipeline-tests"
    type: "test"
    depends-on: ["001", "002", "003"]
  - id: "005"
    subject: "Verify acceptance criteria"
    slug: "verify-pipeline-acceptance"
    type: "test"
    depends-on: ["004"]
```

## Task File References

- [Task 001: Create pipeline engine](./task-001-create-pipeline-engine.md)
- [Task 002: Create worker loop](./task-002-create-worker-loop.md)
- [Task 003: Create pipeline API](./task-003-create-pipeline-api.md)
- [Task 004: Write pipeline tests](./task-004-write-pipeline-tests.md)
- [Task 005: Verify acceptance](./task-005-verify-pipeline-acceptance.md)

## BDD Coverage

All acceptance criteria from ZEN-30 Linear issue are covered:
- "Backend can create a test pipeline with multiple StepRuns" → Task 001, 004
- "Worker can claim and complete a mock step" → Task 002, 004
- "Failed step can be retried" → Task 002, 004
- "StepRun states are observable through API" → Task 003, 005

## Dependency Chain

```
001 (engine) ──┬──> 002 (worker) ──┬──> 004 (tests) ──> 005 (acceptance)
               └──> 003 (api)   ──┘
```

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
