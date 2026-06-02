# Task 003: Create pipeline API endpoints

**Type:** impl
**Depends-on:** ["001"]

## BDD Scenario

```gherkin
Scenario: Create a pipeline via API
  Given the API is running with valid API key
  When I POST /api/pipelines with pipeline_type and step_defs
  Then a PipelineRun is created
  And the response contains pipeline_run_id and status "pending"

Scenario: Get pipeline status
  Given a pipeline exists with id "PR-001"
  When I GET /api/pipelines/PR-001
  Then the response contains pipeline_run_id, status, current_step, and step_runs

Scenario: Get step runs for a pipeline
  Given pipeline "PR-001" has 5 step runs
  When I GET /api/pipelines/PR-001/steps
  Then a list of 5 step runs is returned with status, step_key, and depends_on
```

## What to Implement

Create `backend/app/api/routes/pipelines.py` with:
- `POST /api/pipelines` — create pipeline with step definitions
- `GET /api/pipelines/{pipeline_run_id}` — get pipeline status with step runs
- `GET /api/pipelines/{pipeline_run_id}/steps` — list step runs for a pipeline

Register the router in `backend/app/api/routes/__init__.py`.

## Files to Create

- `backend/app/api/routes/pipelines.py`

## Files to Modify

- `backend/app/api/routes/__init__.py` — add pipelines router

## Verification

```bash
cd backend && python -c "
from app.api.routes.pipelines import router
print('Pipeline routes imported OK')
"
```

Expected: Import succeeds, exit code 0.
