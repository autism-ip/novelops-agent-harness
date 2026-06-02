# Task 006: Fix engine rollback and pipeline status on first claim

**Type**: impl
**depends-on**: []

## BDD Scenario

```gherkin
Scenario: Engine preserves record_id during rollback
  Given a PipelineEngine creating a pipeline with 3 steps
  When step 2 creation fails
  Then step 1 is deleted by its Feishu record_id (not business key)
  And the pipeline record is also deleted by record_id

Scenario: Engine rejects duplicate step_key at creation time
  Given step_defs with duplicate step_key "s1"
  When create_pipeline is called
  Then ValueError is raised with "Duplicate step_key"

Scenario: Pipeline status set to running on first step completion
  Given a pending pipeline with a completed first step
  When complete_step advances the pipeline
  Then the pipeline status becomes "running"
```

## Files to Modify

- `backend/app/pipeline/engine.py`
- `backend/tests/test_pipeline_engine.py`

## Steps

1. In `engine.py`:
   - In `create_pipeline`: store Feishu `record_id` from each step creation result in `created_step_ids`, use these for rollback deletion
   - Verify duplicate step_key check uses set comparison (already correct — confirm and add error message with the duplicate key name)
   - In `complete_step`: already sets pipeline to "running" when runnable steps exist — verify this works correctly

2. In `test_pipeline_engine.py`:
   - Add test for rollback using record_id
   - Add test for duplicate step_key rejection with descriptive message
   - Verify existing pipeline status transition tests

## Verification

```bash
cd backend && python -m pytest tests/test_pipeline_engine.py -v
```
