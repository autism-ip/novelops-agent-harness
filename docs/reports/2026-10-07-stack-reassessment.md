# NovelOps issue-to-PR stack: interim requirement audit (2026-10-07)

This is a progress report, not completion approval. The active goal requires actual requirement events, all applicable statement/line/function/branch coverage at 100%, valid review resolution, and safe PR delivery. No issue is marked Done here.

## Authoritative state and delivery map

Linear reports all 13 issues below as **In Review**. GitHub reports all 13 PRs open, each based on the preceding PR branch. Merge order is the row order.

| Linear issue | GitHub issue / PR | Requirement event and evidence scope |
| --- | --- | --- |
| [ZEN-105](https://linear.app/zenhungyep/issue/ZEN-105) | [#21](https://github.com/autism-ip/novelops-agent-harness/issues/21) / [#23](https://github.com/autism-ip/novelops-agent-harness/pull/23) | A domain-ID storage provider reconciles ambiguous writes; current backend-app Feishu CRUD passed 5/5 representative tables twice historically and again on 2026-10-07. V3 feasibility was measured separately; runtime remains on v1. |
| [ZEN-104](https://linear.app/zenhungyep/issue/ZEN-104) | [#20](https://github.com/autism-ip/novelops-agent-harness/issues/20) / [#24](https://github.com/autism-ip/novelops-agent-harness/pull/24) | Deterministic kernel and one writer; current live `create → tick → approve` reached completed with one versioned approval on 2026-10-07. Legacy parent-record-ID errors were fixed. |
| [ZEN-106](https://linear.app/zenhungyep/issue/ZEN-106) | [#22](https://github.com/autism-ip/novelops-agent-harness/issues/22) / [#25](https://github.com/autism-ip/novelops-agent-harness/pull/25) | Artifact, ModelRouter, trace/cost/eval foundations; prior live DeepSeek and Feishu Artifact/Trace replay are recorded in the issue report. Generic model tables are intentionally outside the 16-repository factory. |
| [ZEN-33](https://linear.app/zenhungyep/issue/ZEN-33) | [#6](https://github.com/autism-ip/novelops-agent-harness/issues/6) / [#27](https://github.com/autism-ip/novelops-agent-harness/pull/27) | Public-hotspot ingestion and Feishu persistence; current offline tests pass, historical live evidence remains scoped to its report. |
| [ZEN-34](https://linear.app/zenhungyep/issue/ZEN-34) | [#7](https://github.com/autism-ip/novelops-agent-harness/issues/7) / [#28](https://github.com/autism-ip/novelops-agent-harness/pull/28) | Hotspots controls and responsive UI; prior browser acceptance used the actual API/Harness with synthetic Feishu transport. New all-source frontend coverage instrumentation exposes the missing component/page tests. |
| [ZEN-35](https://linear.app/zenhungyep/issue/ZEN-35) | [#8](https://github.com/autism-ip/novelops-agent-harness/issues/8) / [#29](https://github.com/autism-ip/novelops-agent-harness/pull/29) | Versioned opportunity analysis, risk gate and trace; prior issue report scopes model/runtime evidence. |
| [ZEN-36](https://linear.app/zenhungyep/issue/ZEN-36) | [#9](https://github.com/autism-ip/novelops-agent-harness/issues/9) / [#30](https://github.com/autism-ip/novelops-agent-harness/pull/30) | Candidate title/cover directions and provenance; prior issue report scopes model/runtime evidence. |
| [ZEN-37](https://linear.app/zenhungyep/issue/ZEN-37) | [#10](https://github.com/autism-ip/novelops-agent-harness/issues/10) / [#31](https://github.com/autism-ip/novelops-agent-harness/pull/31) | Human opportunity/title/cover decisions, ApprovalEvents and workflow unlocking; prior issue report scopes browser/runtime evidence. |
| [ZEN-38](https://linear.app/zenhungyep/issue/ZEN-38) | [#11](https://github.com/autism-ip/novelops-agent-harness/issues/11) / [#32](https://github.com/autism-ip/novelops-agent-harness/pull/32) | Approved inputs bootstrap Book and canonical StoryState v1; prior issue report scopes live evidence. |
| [ZEN-107](https://linear.app/zenhungyep/issue/ZEN-107) | [#33](https://github.com/autism-ip/novelops-agent-harness/issues/33) / [#34](https://github.com/autism-ip/novelops-agent-harness/pull/34) | User-approved iOS-inspired responsive UI across existing pages; prior desktop/mobile browser checks are scoped in its report. |
| [ZEN-39](https://linear.app/zenhungyep/issue/ZEN-39) | [#12](https://github.com/autism-ip/novelops-agent-harness/issues/12) / [#35](https://github.com/autism-ip/novelops-agent-harness/pull/35) | Versioned StoryBible, accepted state patch and ChapterBrief; prior DeepSeek/Feishu evidence is in its report. |
| [ZEN-40](https://linear.app/zenhungyep/issue/ZEN-40) | [#13](https://github.com/autism-ip/novelops-agent-harness/issues/13) / [#36](https://github.com/autism-ip/novelops-agent-harness/pull/36) | Prior live DeepSeek + Feishu Writer → Critic → Rewrite → final verifier reached two immutable ChapterVersions and human review. Repeated model quality and current-head live rerun remain unmeasured. |
| [ZEN-41](https://linear.app/zenhungyep/issue/ZEN-41) | [#14](https://github.com/autism-ip/novelops-agent-harness/issues/14) / [#37](https://github.com/autism-ip/novelops-agent-harness/pull/37) | Prior live Feishu/editorial API run with deterministic model fixtures produced constrained RevisionTask, v2, exact approval and final lock; separate browser checks covered desktop/phone controls. The run took 2,677 seconds, a major workflow-latency risk. |

The per-issue reports under `docs/reports/` carry the full event traces, cleanup counts, model/transport distinctions and limitations. A historical event is not claimed as a current-head rerun where upstream code changed afterward.

## Work and verification in this reassessment

- Reproduced and fixed a Feishu-filter injection in `GET /api/pipelines/{id}`. The repository now escapes the path ID and rejects duplicate business keys with 409. A real HTTP regression asserts the outbound filter expression.
- Reproduced and fixed three legacy pipeline parent mutations that passed `pipeline_run_id` where Feishu requires `record_id`: rollback, completion and first Worker claim.
- Added provider/repository cases for blank IDs, duplicate records, pagination, partial/malformed response handling, permission rejection and ambiguous-read failure. The 16 domain repository mappings and filters are exercised. ZEN-106's Artifacts/Traces remain generic stores, explicitly reflected in the downstream test.
- Merged these owning-PR changes and the new frontend coverage tool through every dependent branch, verified each backend/frontend scope and pushed all 13 branch refs. The final branch has **483 passing offline backend tests, 10 credentialed tests deselected, 77 unified Vitest frontend tests**, and passing frontend lint, typecheck and production build.
- On the authorized synthetic Base, the current five-table provider CRUD probe passed **5/5 in 83.29 seconds**; independent reads found no `probe-` rows. The current direct-kernel live approval flow completed with one ApprovalEvent; independent reads found zero PipelineRuns, StepRuns and ApprovalEvents afterward. No secret values entered Git.
- A GraphQL review audit read reviews, discussion and all inline threads for all 13 PRs, including resolved/outdated threads. There are **zero unresolved threads**; all previously valid automated findings have documented fixes and regressions in their owning reports. No human approval is inferred. Latest CI must be associated with each exact PR head; a green ancestor or old head is insufficient.

## Coverage and delivery blockers

The latest code tree at `3241108810e3a26494d8b71fd1d5e0a647e6529e` reports backend **92.99% statements/lines (3,953/4,251), 80.69% branches (907/1,124), 90.42% combined**: 298 missed lines, 217 missing branch arcs and 191 partial branch lines. Fresh raw Python source-function entries are **401/419 = 95.70%**, with **11/11 lambdas** included; the denominator retains seven Protocol declarations. The reproducible measurement and missing definitions are in `backend/tests/function_entry_coverage.py` and `docs/reports/2026-10-09-function-entry-coverage.json`. No empty declarations were called just to increase coverage. All-source frontend coverage includes unimported TS/TSX sources: **58.95% statements (596/1,011), 62.66% lines (537/857), 52.36% functions (155/296), 55.63% branches (627/1,127)**. The HTTP client retains 100% on all four metrics. No new application exclusion, test removal or gate reduction was used; the whole-project 100% target remains open.

The previous live ZEN-41 editorial flow required **2,677 seconds** with deterministic model fixtures and about 1,333 requests in a corresponding stateful transport replay. It verifies correct persisted behavior but leaves continuous-editing performance unresolved. Repeated real-model revision quality, production Base ACL/schema, configured route price/cost accuracy and cross-process writes remain unverified. The app retains a single-writer deployment contract and feature flags.

`npm audit` finds five high alerts in a pre-existing development-only ESLint chain ending at `braces@3.0.3`; production dependency audit reports zero. The [official advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) lists no patched release as checked here. Do not force a breaking Next.js downgrade or hide the finding. GitHub's PR #24 object previously lagged its remote branch (`6ae00a4d` versus `34678bf2`). A meaningful report update made the PR object catch up, and the report-only commit was propagated through all descendants. Exact-head CI on the latest pushed heads must be checked again after this update.

## Earlier 2026-10-08 security verification

The unchanged backend tree passed **420 offline tests, with 9 credentialed tests deselected**, in 50.08 seconds; branch-aware coverage remains **89.98%**. Final frontend head `62e44053` passed **58 Vitest tests**, lint, TypeScript and production build. All-source frontend coverage is **57.99% statements (584/1,007), 61.82% lines (528/854), 50.67% functions (150/296), 51.92% branches (581/1,119)**. The current denominator includes the new controlled login-signing failure and explicit password-error branch. No source file was excluded.

Five new ChapterReviewDesk interaction tests assert historical-version prose/critique and read-only behavior, exact-version approval, trimmed revision constraints, retention/retry of the same uncertain command, and explicit recovery of a corrupt saved command. They render the real component with controlled API/hook boundaries; they are not a live service/browser run. Four session tests exercise real WebCrypto HMAC with expiry, tampering, configuration and cryptography-failure assertions. Five catch-all route tests exercise real signed sessions and route handlers against controlled backend responses.

The route test reproduced a path guard bypass with a valid session: `..\\private` reached the backend after URL normalization. The owning ZEN-34 PR now allows only letters, digits, `_` and `-` in path segments before constructing the backend URL, matching the current backend's literal route/domain-ID contracts. Regressions reject slash, backslash, dot, encoded-dot, query and fragment syntax before fetch, while verifying public health and protected request forwarding. The fix and session tests were merged through each descendant; every frontend branch passed its own tests and build before push. `session.ts`, the catch-all route and `review-state.ts` are each at 100% on all four metrics. This fixes a concrete security defect, while full-source 100% and the full requirement-event audit remain open.


The additional Hotspots tests exercise the actual workbench, resource hook and API client together across pagination/filter resets, manual add/discard, exact collection, authentication, uncertain remount/retry and corrupt-command recovery. The design branch scopes desktop controls to the table because JSDOM does not apply responsive CSS, and adds a separate mobile-card selection/detail test. Native dialog/media-query APIs are polyfilled; HTTP remains a controlled fixture. These tests do not claim real Feishu backend idempotency.

Two further user-visible failures were reproduced and fixed on ZEN-34: wrong passwords showed only generic sign-in guidance, and a missing signing secret escaped the login handler as an exception. The UI now gives explicit password feedback; the route returns 503 without a Cookie for signing/configuration failure. Real WebCrypto route tests verify expiry and secure Cookie attributes. HTTP/resource tests verify AbortController timeout, cleanup, 401 polling stop, transient retries and no late updates after unmount. The HTTP client, resource hook, health indicator and login route now join the earlier three modules at 100% on all four metrics. Full-source coverage remains incomplete because the remaining business UI, shell and backend paths still require tests.

## Latest latency and read acceptance — 2026-10-08

ZEN-39 code `2a58a76a` limits eligible-brief expansion to the latest persisted version. With three versions the actual HTTP fixture measured **22→8 GETs**, with current-state checks and no fallback to an incomplete newest proposal. This passed its own 393 backend/49 frontend tests and was merged through ZEN-40 (`78d31811`, 410 backend/50 frontend tests) into ZEN-41. Both current upstream heads passed CI and have no unresolved review threads.

ZEN-41 code `fb2c111a` shares only validated immutable Artifact payloads within one review response. The controlled profile measured **31→27 GETs for v1** and **35→31 for v2**. Every refresh and mutation starts fresh; a tampered remote payload prevents both refresh and approval, and restoration recovers the next view. Exact-head CI passed with no unresolved review threads.

A new actual Feishu read at that backend code seeded 21 local-workflow-generated synthetic rows in the approved Base only after checking absence, then read the mounted authenticated review API. The exact chapter/Bible/brief/snapshot/verifier/history matched; unauthenticated access was rejected. **27 real GETs took 65.460 seconds**. Cleanup had no failures and a new independent app-identity client found **zero remaining rows**. This verifies persisted read acceptance for that synthetic case, not live model generation, a deployed frontend or acceptable continuous-editing latency.

The real delay exposed the browser's ten-second abort. Code `4bc60bb1` permits only the review GET to wait up to 120 seconds and declares the same server proxy execution budget. The Next build manifest confirms the budget; actual hosting limits remain unverified. A controlled 65.46-second response now renders in the real component/hook/client, while a hung read still stops at the deadline. A mounted HTTP revision→approval→final-lock test verifies exact commands and retention of v1. The latest tree passed **425 backend and 60 frontend tests**, frontend lint/types/build and Ruff. Coverage above is measured on this tree; named-function collection used a profiling plugin and full-suite pass, without modifying app behavior or coverage settings. The detailed [ZEN-41 report](2026-09-29-chapter-review.md) distinguishes each evidence boundary.

## Decision and next work

**Verified facts:** tests, coverage numbers, current Feishu probes, cleanup, current Linear status, open PR map and review-thread counts above. **Engineering judgment:** the stack is suitable for continued code review but not Done, safe merge, or production enablement under the active goal. **Unverified assumptions:** issue-specific event behavior at every current head, production latency and ACL, and repeated real-model quality. **Next actions:** await exact-head CI on the refreshed PR stack; add meaningful backend and full-source frontend behavioral tests until every applicable metric is 100%; measure Python function coverage; reduce Feishu read amplification and verify an acceptable editorial response time; then re-run exact-head CI, issue event checks and review audit. The existing personal `issue-pr-delivery` Skill was extended with reusable PR-SHA and stale Next generated-type checks; no new Skill was created.


## Native read correctness and performance follow-up (2026-10-09)

- A fresh root-provider probe proved the old GET formula falsely reported absence
  for a quote/backslash ID that native search returned. Owning PR #23 now uses
  structured search for single string IDs and 50-ID chunked batch reads. It rejects
  malformed envelopes/rows, mismatched/duplicate business IDs and cyclic pagination,
  converts text segments and numeric cells, and preserves write reconciliation.
- The real provider repeat passed in 39.69s: two present IDs plus one missing ID
  returned in one search POST / 0.869s. Special-character ensure replay created no
  row. Three probe rows were independently confirmed absent after cleanup. The
  initial false-absence row was separately targeted and independently removed; a
  later SSL auth EOF occurred before any write and was not hidden.
- PR #25 adds Artifact batch reads with identical integrity checks and fresh-call
  semantics. Owning downstream tests continue asserting actual creates, blocked
  ambiguous recovery and no repeated writes; POST search is explicitly read-only.
- All 13 branches were synchronized in dependency order, each at its own backend,
  frontend-test (where configured), Ruff and frontend lint/types/build scope. One
  module-description conflict preserved both StoryState mapping and safe-read notes.
  Every pushed dependency head passed both CI runs; the newest PR #37 code head
  was still awaiting its aggregate checks at the audit immediately after push.
- PR #37 batches immutable sources/history and RevisionTask run statuses within one
  response. The controlled full editorial path lowered review requests **27→22**
  for v1 and **31→23** for v2; generation, revision, approval and lock counts were
  unchanged. Refresh/decision tampering, missing-Artifact restoration, optional
  Critic absence and empty-history assertions remain behavior-based.
- The fresh mounted review API using real Feishu passed **1/1 in 279.25s** at code
  `404cd7cdee01833bec608a3a190c4bc33611872c`: **22 read requests / 26.703s**, complete
  immutable sources/usage verified, **21 seeded rows cleaned**, independent residual
  count **0**, no real model call. The earlier equivalent case was 27 GETs/65.460s;
  these separate single observations are not a p95 or controlled latency benchmark.
- Remaining gates: 100% all applicable coverage metrics; current complete live
  generation/editorial and frontend write-path timing; repeat domain-model evals;
  deployed-proxy/platform duration/production ACL verification; fresh CI/review
  audit at the final report-only head. No issue is declared Done or safely mergeable.
- Reuse assessment: existing `issue-pr-delivery` plus `lark-openapi-explorer` cover
  this work. No new personal Skill is needed for one provider-specific optimization.


## 2026-10-09 editorial timeout and replay follow-up

- Owning ZEN-41 PR #37 fixes valid slow editorial POSTs, deadlines covering JSON
  bodies and the real empty-note replay defect. Precise targets/editors/non-empty
  notes retain their conflict semantics; explicit replay never creates a second
  event. See the issue report for failed and successful probe scopes.
- Mounted real Feishu approval **34.463s/30 requests**, lock **25.398s/26** confirmed
  the ten-second UI deadline mismatch. Current component/client regressions cover
  four slow actions, bounded expiry, exact saved-command recovery and read-only
  history after final lock. Full local gates and current metrics appear above.
- The first production-proxy startup failure required cleanup recovery of 19
  stable rows and two random traces. They were independently removed. Probe
  cleanup now uses actual-ID journals, immutable builds and finally verification.
  A subsequent approval succeeded but replay returned 409; all 22 rows were cleaned.
  A one-row live probe verified create/search differ for empty optional text.
- Existing `issue-pr-delivery` skill updated and skill-creator validation passed.
  No human approval, production performance, deployment or Done is inferred.

- Current code `3241108810e3a26494d8b71fd1d5e0a647e6529e` completed the actual
  ApiClient → local production Next signed-session proxy → Uvicorn → real Feishu
  routine v1 flow: approve **30.259s/30 calls**, exact replay **22.824s/27 read-only
  calls, zero new writes**, final lock **24.487s/26 calls**. Unsigned requests were
  rejected with 401 and each signed client request sent once. No real model ran.
- All event assertions passed, but the whole probe failed at one initial cleanup
  FeishuAPIError. The full original-ID journal recovery found all 22 rows already
  absent, sent zero further deletes and independently batch-verified zero residual;
  recovery passed in 25.29s. The raw failure and recovery are retained in
  `docs/reports/2026-10-09-editorial-runtime.json`. Owned servers/build copy removed.
- Remaining: full-source 100%, live full generation/revision/selective-gate events,
  real-model evals, browser/deployed-platform/ACL/latency acceptance and new-head CI.
