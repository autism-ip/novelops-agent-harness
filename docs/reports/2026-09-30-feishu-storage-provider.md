# ZEN-105 — Feishu storage provider delivery review

## Goal and delivery

- **Issue:** [ZEN-105](https://linear.app/zenhungyep/issue/ZEN-105/validate-feishu-base-v3-and-refactor-feishu-provider-boundary) / [GitHub #21](https://github.com/autism-ip/novelops-agent-harness/issues/21).
- **PR:** [#23](https://github.com/autism-ip/novelops-agent-harness/pull/23), based on `main`; #24 and its descendants consume this provider boundary.
- **Result:** `StorageProvider` hides Feishu record IDs, rejects missing/duplicate business keys, and reconciles ambiguous creates by stable key without a second POST. The adapter remains on official `bitable/v1` OpenAPI; v3 capabilities were measured separately. No second primary database was introduced.

## Verified facts

- The backend app's tenant token read all five representative test tables. First, missing read scopes caused `99991672`. After scopes were granted, reads passed but writes returned `91403` until that same app was added as an `edit` collaborator to the [authorized synthetic Base](https://fcnaul7kb1kf.feishu.cn/base/T8I6buCMoaiLB6srVBrc9i2jnph). The Base has no advanced permissions. The CLI bot identity is a different application. PipelineRuns, StepRuns and ApprovalEvents now have the fields needed for the separate ZEN-104 workflow probe.
- Backend-app `bitable/v1` create, replayed `ensure`, read, update and delete passed for PipelineRuns, StepRuns, ChapterVersions, ReviewReports and ApprovalEvents on two live runs (5/5 each). The second run took 88.41 seconds; per-table CRUD time was 12.69, 11.30, 12.83, 16.37 and 11.34 seconds respectively. Independent reads found zero rows in every test table after both runs.
- Backend-app v3 create/read/PATCH/delete passed in `RuntimeProbe`: PATCH changed only `version` from 1 to 2 and preserved `domain_id`, `kind` and `payload`. A follow-up search found zero remaining patch probes. v3 uses a top-level write field map and returns `record_id_list`; the runtime's v1 adapter uses its separate documented envelope.
- A bounded read burst of 12 v1 lists, with at most four concurrent calls, passed 12/12: 3.37 seconds wall time, 1.04 seconds median request and 1.29 seconds maximum. A separate two-writer same-record probe previously showed a lost logical update, so numeric `version` is not server-side compare-and-swap.
- User-identity v3 probes previously covered 35 batch creates, seven partial updates, pagination, delayed record history, delete, and exact round-trip of a 50,000-character Chinese chapter payload. These are feasibility measurements, not a platform ceiling.
- A production `HarnessKernel.create → tick → decide` probe exposed two v1 response details that the business-key CRUD suite had not exercised: PUT returns only changed fields, and GET/list returns Number cells as strings. The repository now merges partial PUT responses with the previously resolved record and normalizes known numeric fields on read. The stateful HTTP fixture reproduces both shapes. The retried live workflow reached `completed`, stored one versioned approval event, and deleted its PipelineRuns, StepRuns and ApprovalEvents rows afterward (100.56 seconds total). Workflow evidence belongs to [ZEN-104's report](2026-09-30-harness-kernel.md).
- Offline backend after both fixes: `190 passed, 9 integration tests deselected`, 88.30% coverage against an 87.815587% floor. Live business-key CRUD suite: 5/5 passed twice after ACL repair. JUnit preserved per-test `crud_seconds` but emitted five xunit2 compatibility warnings. PR #23 had no review submissions, discussion comments or inline threads when checked; all ten CI jobs at an earlier head passed; recheck the final head before merge.

## Implementation and decisions

- `backend/app/storage.py` owns domain-ID lookup, replay, missing/duplicate behavior and ambiguous-write handling. `backend/app/feishu/repositories/base.py` owns the v1 field mapping and record transport. `backend/app/feishu/client.py` owns tenant-token and API error handling. `backend/tests/test_storage_live.py` is opt-in and requires a disposable Base.
- A stateful HTTP regression reproduces a remote create that committed before a malformed 2xx reply. It verifies one stored record and one POST. This fixed earlier raw `KeyError`/false-success paths without weakening assertions.
- `.env.local` and `.env.*.local` are ignored in PR #23 because the operator's local `backend/.env.local` contains credentials. The approved Base token and five table IDs were added to that local file; no credential values enter Git. This test runner loaded it explicitly because the integration module reads `os.environ`.
- Rollout remains additive: preserve legacy IDs and snapshots, backfill with reviewed mappings, run one writer and retain data for rollback. The provider contract permits a later PostgreSQL implementation without changing domain/workflow code.

## Interpretation and limits

The measured workload supports Feishu as a practical single-user SSOT for the tested operations. The provider PR can be reviewed independently of enabling the full runtime. **Production rollout remains gated** on production Base ACL and complete schema checks: ChapterVersions and ReviewReports were exercised only with their business-key fields; the three workflow tables were expanded for the synthetic Harness probe. Absolute payload and rate ceilings, cross-process conflict behavior and a real post-commit network ambiguity were not induced. The latter is covered by stateful transport tests. Do not infer multi-writer safety from the successful bounded read burst.

## Review, security and follow-up

- No current review comment required code changes at the audit. The only live failure was authorization configuration, resolved with the app's edit access to the synthetic Base. No probe records remained after cleanup.
- Security risk: accidental local-secret commit is reduced by Git ignore rules; deployment must still supply the intended app credentials and Base permissions through a secret manager or process environment. The local file is mode 0600 and is not copied into the PR.
- The existing personal `issue-pr-delivery` Skill was updated earlier to require post-commit malformed-response/timeout fault injection for non-idempotent writes. No new Skill is justified by this single provider-specific probe.
- Follow-up: verify production table fields and ACL before enabling `HARNESS_ENABLED`; retain single-writer operation; measure higher rate and size ceilings only if actual workload needs them. See [feasibility matrix](../feishu-provider-feasibility.md) for the probe protocol and raw limitations.

## Follow-up: bounded retry for a live read error

During downstream ZEN-40/41 synthetic acceptance on 2026-09-30, StoryBible approval and ChapterBrief eligibility passed again, but a Feishu `1255001 InternalError` interrupted the chapter context stage before any chapter run, snapshot or ChapterVersion was created. The probe cleaned 1 ApprovalEvent, 7 Traces, 5 StepRuns, 2 PipelineRuns, 2 StoryStates, 6 Artifacts and 1 Book. Immediate backend-app reads of ChapterVersions, PipelineRuns, StepRuns, StoryStates, Artifacts, Books and RevisionTasks all succeeded afterward; this is consistent with a transient service response, though the failing endpoint was not captured.

`FeishuClient` now retries that **specific business code on GET only**, at most twice with short backoff. POST, PUT and DELETE are never automatically replayed: their ambiguous outcomes remain subject to the storage provider's business-key reconciliation. Client tests prove both recovery and bounded exhaustion, and that a POST returning the same code is sent only once. The client suite passed 20 tests; the full offline backend suite passed **192 tests**, with 9 credentialed integration tests deselected and approximately **88%** statement coverage above the existing gate. The exact-head CI and a repeated live chapter run remain to be checked. This change does not imply that all Feishu internal errors are transient or that writes are safe to retry.

## Follow-up: bounded transport retry and cleanup recovery

The next downstream live probe encountered `httpx` GET read timeouts during StoryBible work and then intermittent DNS resolution errors while trying to clean its synthetic rows. This was a transport failure, distinct from Feishu's JSON `1255001` response. After connectivity returned, a journal-identified cleanup deleted 1 ApprovalEvent, 4 Traces, 3 StepRuns, 1 PipelineRun, 2 StoryStates, 3 Artifacts and 1 Book belonging to that run. A separate read confirmed the test Base's workflow tables were accessible again. No unrelated retained Book or StoryState was selected for deletion.

`FeishuClient` now uses the same two-retry limit for **GET transport errors** as for GET `1255001`, with short backoff. A persistent error still raises `FeishuAPIError`; POST, PUT and DELETE still receive no automatic transport retry. A regression covers GET timeout recovery, bounded persistent connection failure, and exactly one POST after a write-response timeout. The client suite passes 21 tests; the full offline backend suite passes **193 tests**, with 9 credentialed tests deselected and approximately **88%** coverage. This improves resilience to brief read faults; it cannot make a prolonged outage available. The exact-head CI and another live workflow are pending.

## Re-audit on 2026-10-07: provider contract and pipeline read integrity

The active delivery objective now requires 100% statement, line, function and branch coverage for applicable code, plus requirement events and runtime proof. This section records current evidence without treating the PR as finished.

- A full offline backend run at this local head passed **228 tests**; **9 live integration tests were deselected**. Coverage.py with branch measurement reported **1,055 statements, 51 missed lines, 222 branches, 20 partially covered branch lines, 94.13% combined coverage** (`BACKEND_API_KEY=ci-contract-key python -m pytest tests -q -m 'not integration' --cov=app --cov-branch --cov-report=json:/tmp/zen105-coverage-current.json --cov-report=term`). The Feishu client, generic repository, 16 concrete repositories, factory and provider are at 100% line/branch coverage in this run. Function coverage has not yet been measured; neither has this head been run against live Feishu. The 100% objective is therefore **open**.
- New behavioral cases reject blank domain IDs before a remote read, detect duplicate business keys and invalid pagination, preserve blank numeric cells, reject malformed update echoes, stop on definite 403 writes, and stop safely when ambiguous update reconciliation cannot read. The repository factory and domain query tests exercise every configured table, path and filter against a stateful fake transport.
- A failing HTTP regression reproduced a pipeline query that interpolated an untrusted path ID directly into a Feishu filter. The GET route now uses the repository's JSON-escaped business-key lookup, returns 404 for absence, and returns 409 for duplicate IDs. The regression checks the exact escaped filter sent to the Feishu client. This avoids broadening a lookup through injected filter syntax and prevents silently selecting an arbitrary duplicate.
- The current run is offline and does not establish v3 runtime migration, absolute rate or size ceilings, post-commit network failure, deployment ACL, or end-to-end behavior at this head. The remaining coverage is mainly pipeline engine/worker behavior and duplicate legacy API modules; those require requirement-based review rather than exclusions or gate reduction.

## Live provider rerun on 2026-10-07

At the current provider commit `6bdec7be`, the opt-in `tests/test_storage_live.py` suite ran against the user-authorized synthetic Base using the backend application's configured identity. All **5/5** collection cases passed in **83.29 seconds**: PipelineRuns, StepRuns, ChapterVersions, ReviewReports and ApprovalEvents each completed create, replay, read, update and delete. A separate subsequent read of all five tables found **zero** remaining `probe-` IDs. The configured Base token was checked against the authorized Base before writes; no secrets were printed or committed. This verifies this bounded live CRUD path, not the new 100% coverage goal or v3 runtime migration.

## Native batch reads and literal business IDs (2026-10-09)

The official record-search API was read through `llms.txt` → cloud-document index →
[search specification](https://open.feishu.cn/document/docs/bitable-v1/app-table-record/search.md).
`StorageProvider.get_many` now performs bounded, structured OR queries: 50 business
IDs per chunk, 500 records per page, deduplicated inputs and deterministic result
order. Missing IDs remain absent. All pages must pass envelope, record, business
identity, uniqueness and pagination checks before returning. The adapter converts
ordered text segments and Number cells to the existing domain format and keeps
platform record IDs private. This is not a multi-page atomic snapshot.

The first application-identity live probe found a real incompatibility in the old
JSON-escaped GET formula: a key containing both a quote and backslash was stored
and returned by structured search, but the old single-key lookup reported absence.
The original cleanup therefore did not see that one row. A targeted structured
lookup deleted that exact probe row by its verified platform identity, and a new
independent client confirmed zero remaining rows for all three probe keys.
Single string business-key lookup (including the legacy pipeline API and worker
claim lookup) now uses the same structured search, so ensure/reconciliation cannot
mistake that valid literal key for absence. Compound/numeric legacy query behavior
is retained and tested. The subsequent probe attempt failed at token acquisition
with an SSL EOF before any record write; auth retry semantics were not relaxed.

Local root-PR verification: **276 offline tests passed**, **10 opt-in integration
cases deselected**; Ruff 0.16.9 and frontend lint/typecheck/production build passed.
Coverage.py, with the same complete `app` source and branch measurement, reports
**1,053/1,104 statements/lines (95.38%)**, **224/248 branches (90.32%)**, and **94.45%
combined**. Client, generic repository and concrete provider are each at **100%
statement/line/branch coverage**. Function coverage is not established for this
root head. Existing no-blind-replay write assertions remain in force; they classify
`/records/search` as a read-only POST rather than counting it as a record creation.
The 100% whole-project and complete runtime acceptance objectives remain open.

The final application-identity repeat passed **1/1** in **39.69 seconds**, including
preflight, three synthetic writes and cleanup. A batch requesting two present IDs
plus one absent ID used **one read-only POST in 0.869 seconds**. Quote/backslash/
Chinese-key ensure replay issued **zero record creates**. Rich-text and numeric
roundtrips passed, and a fresh independent client observed **zero remaining probe
rows**. These timings describe this small probe, not the chapter desk or platform
limits. Exact-head CI remains pending immediately before push. Batch consumption
and chapter-desk latency will be verified in their owning PRs.
