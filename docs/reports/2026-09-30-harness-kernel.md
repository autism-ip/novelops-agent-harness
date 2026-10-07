# ZEN-104 — Harness kernel delivery review

## Delivery

- **Issue:** [ZEN-104](https://linear.app/zenhungyep/issue/ZEN-104) / [GitHub #20](https://github.com/autism-ip/novelops-agent-harness/issues/20).
- **PR:** [#24](https://github.com/autism-ip/novelops-agent-harness/pull/24), stacked on the Feishu provider [#23](https://github.com/autism-ip/novelops-agent-harness/pull/23).
- **Contract:** one persistent workflow writer, deterministic run/step IDs, durable creation-intent markers, explicit state transitions and versioned approvals. The kernel uses Feishu as its record store.

## Verification

- Offline backend after the Feishu v1 response-shape fixes: `209 passed, 9 integration tests deselected`, 90.00% coverage against an 87.815587% floor. Tests exercise replay, version conflicts, restart recovery, completion, approval idempotency, failed handlers and lifecycle composition through the real HTTP client/repository fixture.
- On 2026-09-30, a synthetic live probe used production `build_runtime`, `HarnessKernel`, `FeishuClient`, `BaseRepository` and `FeishuStorageProvider` against the [authorized test Base](https://fcnaul7kb1kf.feishu.cn/base/T8I6buCMoaiLB6srVBrc9i2jnph). It first required PipelineRuns, StepRuns and ApprovalEvents to be empty, then created a one-step service workflow with an approval gate. `create` returned a pending run and step; `tick` produced `awaiting_approval` with integer `output_version=1`; `decide(approve, 1)` completed the run and persisted exactly one ApprovalEvent with `target_version=1`.
- The probe took 100.56 seconds including all Feishu requests and cleanup. The one temporary row in each of PipelineRuns, StepRuns and ApprovalEvents was deleted in `finally`; all three cleanup calls succeeded. No secret values or model payloads were written to this report.
- Earlier live attempts exposed real v1 adapter defects: a partial PUT reply omitted unchanged business fields, and GET/list returned Number cells as strings. Both fixes and stateful regressions belong to the provider PR #23. This report records the successful rerun after those fixes.

## Limits and release conditions

The live probe called `kernel.tick()` directly rather than starting the background scheduler or going through the HTTP API. Those paths are covered by the offline lifecycle tests but have not yet been exercised against the live Base. The test Base has the three workflow table schemas needed by this probe; it does not establish that every production table, ACL and model route is ready. Run one backend writer and keep the journal directory across restarts. Resolve any ambiguous Feishu write before resuming work.

The issue's acceptance is met for deterministic execution and versioned approvals in the verified single-writer scenario. Keep broader product rollout gated on the remaining stacked issues and production configuration checks.

## Re-audit on 2026-10-07: parent record identity

Three regressions first failed against the existing legacy `PipelineEngine` / `WorkerLoop`: partial creation rollback deleted the parent using its domain ID, completing a step updated the parent using its domain ID, and first worker claim read/updated the parent using its domain ID. The Feishu repository CRUD contract requires `record_id` for get/update/delete. The fixes use the parent create response or resolve the unique parent by `pipeline_run_id` before mutation. The old first-claim test was updated to provide a valid Feishu `record_id` and now asserts that ID, preserving the stronger real contract. The v0.2 `HarnessKernel` continues to use the provider's domain-ID interface.

The focused engine/worker suite passed **49 tests**. The complete offline backend suite at this local head passed **250 tests**, with **9 opt-in live integration tests deselected**. Branch-aware coverage is **93.42%** (1,477 statements, 76 missed lines, 348 branches, 40 partially covered branch lines). Function coverage, live runtime at this head, and the new 100% line/function/branch objective remain open. These results extend the prior single-writer verification; they do not establish readiness under the new goal.

## Live kernel rerun on 2026-10-07

The configured backend identity and Base token were checked against the user-authorized synthetic test Base; its PipelineRuns, StepRuns and ApprovalEvents tables were empty before the run. Production `build_runtime(Settings)` created a unique one-step service workflow with an approval gate. `HarnessKernel.create` returned a pending run, `tick` reached `awaiting_approval` with exactly one step at `output_version=1`, and `decide(approve, 1)` completed the run with exactly one ApprovalEvent for that version. The script deleted its ApprovalEvent, StepRun and PipelineRun in `finally`; a separate read confirmed **0 rows** in all three tables afterward. This verifies the direct-kernel live path at `6ae00a4d` plus the current provider base. It does not exercise a live background scheduler or HTTP server, and the new 100% coverage objective remains open.

## 2026-10-07 review and PR-head audit

All five automated inline review threads on PR #24 are resolved, including deterministic step ordering, sibling terminalization, status-read cost, invalid handler output and missing-handler recovery. No new discussion comments or review submissions were present beyond the documented review. The remote branch ref contains the live rerun report at `34678bf2`, but GitHub's PR object still advertised older head `6ae00a4d` during the stack audit; exact-head CI and diff isolation remain pending until GitHub reports the same SHA as the branch ref. This metadata discrepancy is separate from the runtime result and is not treated as acceptance evidence.

After pushing `af20f9df`, GitHub's PR #24 head SHA matched the remote branch ref. The stale PR metadata condition is resolved; CI for this new report head must still be checked independently.
