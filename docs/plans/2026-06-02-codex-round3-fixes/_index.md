# Codex Round 3 Review Fixes — ZEN-29 + ZEN-30

## Context

Codex automated review identified 20 issues across PR #15 (ZEN-29) and PR #16 (ZEN-30).
Root cause analysis reveals **3 systemic issues** that manifest in multiple review comments:

1. **Business key != Feishu record_id**: `step_run_id` is a business field stored in Bitable records, but `BaseRepository.update()` expects a Feishu `record_id`. This causes `claim_step`, `worker.claim_step`, and `engine.complete_step` to fail against the real API.
2. **Broad exception swallowing**: `base.py get()` catches all exceptions as `None`, hiding auth/network failures.
3. **Missing domain exceptions**: `client.py` raises `httpx.HTTPStatusError` for 4xx/5xx instead of domain-specific `FeishuAPIError`.

## Current-State vs Target-State

| Dimension | Current (ZEN-30) | Target |
|-----------|-----------------|--------|
| `base.py get()` | `except Exception: return None` | Only catches `FeishuNotFoundError` |
| `base.py` helpers | No `_field_filter`, no `find_by_business_key` | Both present |
| `step_runs.claim_step` | Passes `step_run_id` as record_id | Resolves to Feishu record_id first |
| `step_runs.find_by_pipeline` | Hardcoded f-string filter | Uses `_field_filter()` |
| `client.py` errors | `httpx.HTTPStatusError` for 4xx/5xx | `FeishuAPIError` domain exception |
| `worker.claim_step` | Unconditional update | CAS: checks lease_owner before claim |
| `worker.execute_step` | No lease recheck before complete | Rechecks lease expiry before complete |
| Pipeline status | Manual `running` set in engine | Auto-set `running` on first step claim |
| `.env.example` | Missing table ID placeholders | All 16 `FEISHU_TABLE_ID_*` present |
| `pyproject.toml` | Missing `asyncio_mode` | Restored |

## Scope Decisions

**In scope** (actionable, concrete):
- All 6 ZEN-29 issues
- 10 of 14 ZEN-30 issues (P1s + P2s with clear fixes)

**Out of scope** (design decisions / new features / stale):
- `pipelines.py:94` — GET /api/pipelines collection endpoint (new feature)
- `pipelines.py:113` — Event loop blocking (sync Feishu calls are by design; async refactor is a separate initiative)
- `pipelines.py:59` — Client lifecycle (FastAPI dependency injection pattern is intentional)
- `step_runs.py:42` — "running" status (already fixed in current code, stale comment)

## Execution Plan

```yaml
tasks:
  - id: "001"
    subject: "Fix base.py exception handling and add _field_filter"
    slug: "fix-base-exception-and-field-filter"
    type: "impl"
    depends-on: []

  - id: "002"
    subject: "Add find_by_business_key lookup to BaseRepository"
    slug: "add-find-by-business-key"
    type: "impl"
    depends-on: ["001"]

  - id: "003"
    subject: "Add domain exceptions and transport error classification to client"
    slug: "add-domain-exceptions"
    type: "impl"
    depends-on: []

  - id: "004"
    subject: "Fix step_runs to use record_id and _field_filter"
    slug: "fix-step-runs-record-id"
    type: "impl"
    depends-on: ["001", "002"]

  - id: "005"
    subject: "Make worker claims CAS-aware with lease recheck"
    slug: "worker-cas-lease-recheck"
    type: "impl"
    depends-on: ["002", "003"]

  - id: "006"
    subject: "Fix engine rollback and pipeline status on first claim"
    slug: "fix-engine-rollback-and-status"
    type: "impl"
    depends-on: []

  - id: "007"
    subject: "Update config files (.env.example, pyproject.toml)"
    slug: "update-config-files"
    type: "config"
    depends-on: []

  - id: "008"
    subject: "Run full test suite and verify all fixes"
    slug: "verify-all-fixes"
    type: "test"
    depends-on: ["001", "002", "003", "004", "005", "006", "007"]
```

## Task File References

- [Task 001: Fix base.py exception handling](./task-001-fix-base-exception-and-field-filter.md)
- [Task 002: Add find_by_business_key](./task-002-add-find-by-business-key.md)
- [Task 003: Domain exceptions](./task-003-add-domain-exceptions.md)
- [Task 004: Fix step_runs](./task-004-fix-step-runs-record-id.md)
- [Task 005: Worker CAS](./task-005-worker-cas-lease-recheck.md)
- [Task 006: Engine fixes](./task-006-fix-engine-rollback-and-status.md)
- [Task 007: Config files](./task-007-update-config-files.md)
- [Task 008: Verify](./task-008-verify-all-fixes.md)

## BDD Coverage

All tasks include self-contained BDD scenarios in their task files. See individual task files for Given/When/Then specifications.

## Dependency Chain

```
001 (base.py fixes) --> 002 (find_by_business_key) --> 004 (step_runs) --+
003 (domain exceptions) ---------------------------> 005 (worker CAS) --+
006 (engine fixes) ----------------------------------------------------+
007 (config) ----------------------------------------------------------+
                                                                       v
                                                              008 (verify all)
```
