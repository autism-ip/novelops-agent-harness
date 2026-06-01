# Task 004: Fix step_runs to use record_id and _field_filter

**Type**: impl
**depends-on**: ["001", "002"]

## BDD Scenario

```gherkin
Scenario: claim_step resolves business key to record_id before updating
  Given a StepRunsRepo with record {step_run_id: "SR-001", record_id: "rec-abc", status: "pending"}
  When claim_step("SR-001", "worker-1") is called
  Then find_by_business_key is called with step_run_id="SR-001"
  And update is called with record_id="rec-abc" (not "SR-001")
  And the update sets status="running" and lease_owner="worker-1"

Scenario: find_by_pipeline uses _field_filter
  Given a StepRunsRepo
  When find_by_pipeline("PR-001") is called
  Then list is called with filter_expr from _field_filter(pipeline_run_id="PR-001")
```

## Files to Modify

- `backend/app/feishu/repositories/step_runs.py`
- `backend/tests/test_step_runs.py` (create if not exists)

## Steps

1. In `step_runs.py`:
   - Change `find_by_pipeline` from hardcoded f-string to `self._field_filter(pipeline_run_id=pipeline_run_id)`
   - Change `claim_step` to first call `self.find_by_business_key(step_run_id=step_run_id)` to get `record_id`, then call `self.update(record["record_id"], ...)` with status="running" and lease_owner
   - Raise `ValueError` if step_run_id not found

2. Create/update `test_step_runs.py`:
   - Mock the BaseRepository methods
   - Test `claim_step` resolves business key to record_id
   - Test `find_by_pipeline` uses `_field_filter`

## Verification

```bash
cd backend && python -m pytest tests/test_step_runs.py tests/test_worker_loop.py tests/test_pipeline_engine.py -v
```
