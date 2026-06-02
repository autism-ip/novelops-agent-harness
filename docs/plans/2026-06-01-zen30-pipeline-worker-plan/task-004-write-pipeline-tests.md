# Task 004: Write unit tests for engine and worker

**Type:** test
**Depends-on:** ["001", "002", "003"]

## BDD Scenario

```gherkin
Scenario: PipelineEngine unit tests with mocked repos
  Given a PipelineEngine with mocked PipelineRunsRepo and StepRunsRepo
  When create_pipeline is called with 3 step_defs
  Then pipeline_repo.create is called once
  And step_repo.create is called 3 times
  And the returned pipeline has status "pending"

  When get_runnable_steps is called
  Then only steps with all dependencies met and status "pending" are returned

  When complete_step is called
  Then step_repo.update sets status to "success"

Scenario: WorkerLoop unit tests with mocked engine
  Given a WorkerLoop with a mocked PipelineEngine
  When poll_once is called and a runnable step exists
  Then the step is claimed with lease_owner and lease_until
  And the returned dict has step_run_id and status "running"

  When execute_step is called with a successful handler
  Then engine.complete_step is called

  When execute_step is called with a failing handler
  Then engine.fail_step is called with the error message

Scenario: Pipeline API endpoint tests
  Given a FastAPI TestClient with mocked PipelineEngine
  When POST /api/pipelines is called
  Then 201 is returned with pipeline_run_id

  When GET /api/pipelines/{id} is called
  Then 200 is returned with pipeline details
```

## What to Implement

Create `backend/tests/test_pipeline_engine.py` — test PipelineEngine with mocked repos.
Create `backend/tests/test_worker_loop.py` — test WorkerLoop with mocked engine.
Create `backend/tests/test_pipeline_api.py` — test API endpoints with TestClient.

## Verification

```bash
cd backend && python -m pytest tests/test_pipeline_engine.py tests/test_worker_loop.py tests/test_pipeline_api.py -v
```

Expected: All tests pass, exit code 0.
