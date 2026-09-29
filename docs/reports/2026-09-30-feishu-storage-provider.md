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
