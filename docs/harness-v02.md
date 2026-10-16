# Harness v0.2 — ZEN-104 / #20

## Production entry point

Run one process: `uvicorn app.main:app --host 127.0.0.1 --port 8000` from backend.
Set `BACKEND_API_KEY`, `HARNESS_ENABLED=true`, `FEISHU_APP_ID`,
`FEISHU_APP_SECRET`, `FEISHU_APP_TOKEN`, and table IDs for PIPELINE_RUNS,
STEP_RUNS and APPROVAL_EVENTS. With HARNESS_ENABLED=false, health/config and
legacy APIs remain available; the scheduler is explicitly not started.

Add the following fields to the existing schema before enabling:

- PipelineRuns: `definition_json` (text).
- StepRuns: `handler`, `kind`, `input_json`, `output_json` (text),
  `requires_approval` (checkbox), `output_version` (number).
- ApprovalEvents: `target_version` (number).

Keep existing IDs, fields and historical rows. Legacy rows without a definition
or registered handler are not v0.2 executions; migrate or finish them separately
before enabling the new runtime over the same tables.

## Execution model

FastAPI lifespan builds one kernel/storage instance, recovers interrupted work,
starts its polling thread, and joins it at shutdown. The registry initially
contains a deterministic `noop` handler to exercise deployment without a model.
New tool/semantic workflows register handlers before startup; public requests
cannot name arbitrary Python code. A single reentrant writer lock serializes
API actions, scheduler ticks, handler persistence and approval decisions.
Long handlers serialize requests; optimize only after measuring the single-user
workload. Each external call must have a timeout no longer than the shutdown
budget (35 seconds). Shutdown reports a timed-out handler and retains the lock.

One process lock in HARNESS_JOURNAL_DIR prevents two schedulers using the same
runtime directory. Different directories/hosts cannot coordinate: never run
multiple backends against these tables. This is not distributed election/CAS.

All lifecycle mutations use `_transition`. Runnable dependency selection has one
path, `runnable`, shared by normal operation and recovery. Kinds distinguish tool,
service and agent steps without requiring a fake Agent for deterministic work.

## Idempotency and recovery

Each create requires `request_key`; the run ID is its stable hash and each step
ID derives from run ID + step key. Reusing a key with different inputs returns
409. Partial creation retains a `creating` parent for reconciliation, rather
than silently deleting orphans. All step records must exist before enqueueing.

Before each POST the kernel fsyncs an intent marker under HARNESS_JOURNAL_DIR.
Markers contain only collection/domain identity and are **not a business-data
store**: Feishu remains the SSOT. Preserve this directory across deployments and
restarts. On replay, reconcile an existing Feishu record; if a prior POST may
have occurred but the record is still absent, stop as `blocked`/503. Do not
delete markers as an automatic retry. Operator reconciliation must establish the
remote outcome first. A crash just before sending a POST can therefore require
manual recovery; safety takes precedence over silently creating duplicates.

Running steps interrupted by restart requeue with an incremented bounded retry
counter. Handlers must use stable step/business keys to reconcile external
effects. Non-idempotent external actions must return AmbiguousWrite when their
outcome is unknown. Exhausted retries fail the parent. Persistence failures after
handler success stop the scheduler instead of immediately re-running the tool.
Restart then uses the same stable handler identity and reconciliation contract.

Approvals use exact output versions. Persist a stable ApprovalEvent before
transitioning the step; startup finishes an interrupted approved transition.
Repeated identical decisions are idempotent; opposite/stale decisions return
409. Routine steps continue automatically; only configured gates wait.

## Compatibility and ownership

- Retained: DAG validation, business IDs, Feishu tables, API-key security,
  legacy tests, v0.1 engine/worker modules for migration.
- Deprecated: direct legacy `/api/pipelines` creation when the v0.2 kernel is
  active (410); use `/api/workflows`. Legacy modules are not used by the runtime.
- Removed from v0.2 execution: lease contention, worker election, fake system
  Agents, direct record-ID writes and distributed-CAS assumptions.
- #21 owns storage/identity mechanics; #22 adds artifacts/model traces/usage.

## Verification

`pytest tests/test_harness_kernel.py` uses the real client, mapped repositories,
provider and FastAPI composition with a stateful HTTP fixture that assigns
different Feishu record IDs. It checks startup/shutdown, replay, concurrent
approval, process lock, partial creates, failures and restart recovery. This is
not a claim of live backend-to-Feishu deployment verification.
