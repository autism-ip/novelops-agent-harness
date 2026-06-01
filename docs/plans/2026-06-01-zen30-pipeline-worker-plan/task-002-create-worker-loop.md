# Task 002: Create worker loop with lease-based claiming

**Type:** impl
**Depends-on:** ["001"]

## BDD Scenario

```gherkin
Scenario: Worker claims next runnable step
  Given a pipeline with step A pending and step B blocked by A
  When the worker polls for work
  Then step A is claimed with lease_owner set and status "running"

Scenario: Worker completes a step
  Given the worker has claimed step A
  When the step execution succeeds
  Then step A status becomes "success"
  And lease_owner is preserved

Scenario: Worker handles step failure with retry
  Given a step with retry_count=0 and max_retries=3
  When the step execution fails
  Then step status becomes "failed"
  And retry_count increments to 1
  And the step is re-queued to "pending" for retry

Scenario: Lease expiry allows re-claiming
  Given a step claimed by worker-1 with lease_until in the past
  When worker-2 polls for work
  Then worker-2 can re-claim the expired step
```

## What to Implement

Create `backend/app/pipeline/worker.py` with:
- `WorkerLoop` class:
  - `__init__(self, engine: PipelineEngine, worker_id: str, poll_interval: float = 5.0, lease_duration: int = 300, max_retries: int = 3)`
  - `poll_once() -> dict | None` — find next claimable step, claim it with lease
  - `execute_step(step_run_id, handler: Callable) -> dict` — run handler, complete or fail
  - `claim_step(step_run_id) -> dict` — set lease_owner, lease_until, status="running"
  - `is_lease_expired(step_run) -> bool` — check if lease_until < now

## Files to Create

- `backend/app/pipeline/worker.py`

## Verification

```bash
cd backend && python -c "
from app.pipeline.worker import WorkerLoop
print('WorkerLoop imported OK')
"
```

Expected: Import succeeds, exit code 0.
