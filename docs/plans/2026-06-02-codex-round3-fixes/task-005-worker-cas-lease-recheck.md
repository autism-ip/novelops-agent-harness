# Task 005: Make worker claims CAS-aware with lease recheck

**Type**: impl
**depends-on**: ["002", "003"]

## BDD Scenario

```gherkin
Scenario: Worker claims step only if lease_owner matches or is empty
  Given a step with lease_owner="" and status="pending"
  When worker claims the step
  Then the claim succeeds and sets lease_owner to the worker_id

Scenario: Worker does not claim step owned by another worker
  Given a step with lease_owner="worker-2" and lease not expired
  When worker-1 tries to claim the step
  Then the claim is skipped

Scenario: Worker rechecks lease before completing a step
  Given a step claimed by this worker with an expired lease
  When complete_step is called
  Then a RuntimeError is raised about expired lease
```

## Files to Modify

- `backend/app/pipeline/worker.py`
- `backend/tests/test_worker_loop.py`

## Steps

1. In `worker.py`:
   - In `claim_step`: read current step via `find_by_business_key`, check `lease_owner` is empty or matches `self._worker_id`, only then update
   - In `execute_step`: before calling `engine.complete_step`, recheck lease expiry via `is_lease_expired`
   - When claiming the first step of a pipeline, set pipeline status to "running"

2. In `test_worker_loop.py`:
   - Add test for CAS claim (skips when owned by another)
   - Add test for lease recheck before complete
   - Add test for pipeline status transition to "running"

## Verification

```bash
cd backend && python -m pytest tests/test_worker_loop.py -v
```
