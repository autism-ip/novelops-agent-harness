# Task 005: Verify acceptance criteria

**Type:** test
**Depends-on:** ["004"]

## BDD Scenario

```gherkin
Scenario: Full acceptance — create pipeline, run worker, observe via API
  Given the backend is running
  When I POST /api/pipelines with douyin_to_novel pipeline type and 3 steps
  Then a pipeline_run_id is returned
  And the pipeline status is "pending"

  When the worker loop processes one step
  Then the step status changes from "pending" to "running" to "success"

  When I GET /api/pipelines/{pipeline_run_id}
  Then current_step has advanced
  And step runs show mixed statuses (success, pending)

  When a step fails and retry_count < max_retries
  Then the step is re-queued to "pending" with incremented retry_count

  When I GET /api/pipelines/{pipeline_run_id}/steps
  Then all step states are observable with correct fields
```

## What to Implement

No new files. Run the full test suite and verify all acceptance criteria pass.

## Verification

```bash
cd backend && python -m pytest tests/test_pipeline_engine.py tests/test_worker_loop.py tests/test_pipeline_api.py -v
```

Expected: All tests pass, exit code 0. All 4 acceptance criteria from ZEN-30 are covered by test assertions.
