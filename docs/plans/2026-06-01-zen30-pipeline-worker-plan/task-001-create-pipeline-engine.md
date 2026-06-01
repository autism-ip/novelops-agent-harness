# Task 001: Create pipeline models and engine service

**Type:** impl
**Depends-on:** []

## BDD Scenario

```gherkin
Scenario: PipelineEngine creates a pipeline run with step runs
  Given a PipelineEngine wired to PipelineRunsRepo and StepRunsRepo
  When I call create_pipeline("douyin_to_novel", step_defs, source_hotspot_id="H1")
  Then a PipelineRun is created with status "pending"
  And StepRuns are created for each step_def
  And each StepRun has correct step_key, assigned_agent_id, and depends_on
  And the pipeline's current_step is set to the first step

Scenario: PipelineEngine resolves runnable steps
  Given a pipeline with steps [A, B, C] where B depends on A and C depends on B
  When I call get_runnable_steps(pipeline_run_id)
  Then only step A is returned (no unmet dependencies)

  Given step A is completed
  When I call get_runnable_steps(pipeline_run_id)
  Then only step B is returned

Scenario: PipelineEngine marks step as completed and advances pipeline
  Given a pipeline with current_step = "A"
  When I call complete_step(step_run_id, output_refs=["ref1"])
  Then step A status becomes "success"
  And the pipeline current_step advances to the next runnable step
```

## What to Implement

Create `backend/app/pipeline/__init__.py` — package marker.

Create `backend/app/pipeline/models.py` with:
- `StepDef` dataclass: `step_key: str`, `assigned_agent_id: str`, `depends_on: list[str]`
- `PipelineDef` dataclass: `pipeline_type: str`, `steps: list[StepDef]`

Create `backend/app/pipeline/engine.py` with:
- `PipelineEngine` class:
  - `__init__(self, pipeline_repo: PipelineRunsRepo, step_repo: StepRunsRepo)`
  - `create_pipeline(pipeline_type, step_defs, source_hotspot_id="", book_id="", operator="") -> dict`
  - `get_runnable_steps(pipeline_run_id) -> list[dict]`
  - `complete_step(step_run_id, output_refs=None) -> dict`
  - `fail_step(step_run_id, error_message) -> dict`

## Files to Create

- `backend/app/pipeline/__init__.py`
- `backend/app/pipeline/models.py`
- `backend/app/pipeline/engine.py`

## Verification

```bash
cd backend && python -c "
from app.pipeline.engine import PipelineEngine
from app.pipeline.models import StepDef, PipelineDef
print('PipelineEngine imported OK')
"
```

Expected: Import succeeds, exit code 0.
