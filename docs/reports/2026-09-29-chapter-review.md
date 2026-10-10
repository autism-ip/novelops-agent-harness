# ZEN-41 — Chapter review desk delivery record

## Goal and delivery scope

- [Linear ZEN-41](https://linear.app/zenhungyep/issue/ZEN-41/build-chapter-review-desk-with-selective-approval-and-final-lock) / [GitHub issue #14](https://github.com/autism-ip/novelops-agent-harness/issues/14).
- One [PR #37](https://github.com/autism-ip/novelops-agent-harness/pull/37) for this issue, stacked on [ZEN-40 PR #36](https://github.com/autism-ip/novelops-agent-harness/pull/36), branch `codex/zen-41-chapter-review-desk` targeting `codex/zen-40-chapter-loop`. The initial implementation commit was `16478fe8f3a45a6fff8eb52bc2644732a9708dfa`; later review and live evidence is recorded below. Merge order remains the upstream stack, then ZEN-40, then ZEN-41.
- Adds the book and chapter review desk, exact editorial APIs, persisted RevisionTasks, selective human gates, historical evidence, and final lock. The established Impeccable layout uses a desktop content/decision split, mobile stacking, rounded cards and restrained interaction transitions.

## Implementation and decisions

- `backend/app/chapter_loop.py` records first-N and low Critic score review policy in each run and stops the run if the active configuration drifts; it exposes an exact review state and validates run, version, Artifact and gate version before editorial commands. Routine passes complete automatically. Gated passes await an editor. Generic workflow step decisions cannot bypass chapter-specific version checks.
- Approve/reject persist an idempotent ApprovalEvent and update the selected ChapterVersion; a constrained revision persists a deterministic RevisionTask with source version, source Artifact, frozen request and explicit `must_keep`, `must_change`, `do_not_change`, then enqueues a rewrite. Replays reuse exact commands; conflicting or stale commands fail. Final lock accepts a reviewed or approved current version and blocks later changes while old versions remain.
- The review endpoint returns the current StoryState, StoryBible, Brief and snapshot plus each version's linked Critic evidence and deterministic verification Artifact. The UI changes prose, report, verification and source references together when an older version is selected; current run planning and usage are labeled separately. Historical versions are read-only. A local session storage recovery card retains uncertain commands for exact replay.
- RevisionTasks gain additive Feishu fields documented in `docs/feishu-schema.md`. `docs/chapter-review.md` records the contract and deployment limits.

## Defect found during verification

The first review desk rendering changed prose when a historical version was selected but continued to show the latest Critic report and verifier. The endpoint now supplies evidence per ChapterVersion, and the UI renders that version's evidence. A regression asserts two retained versions have distinct report and verifier Artifact IDs. An empty current run also now shows preexisting legacy versions read-only.

## Verification completed on 2026-09-29

| Check | Result |
| --- | --- |
| Backend `ruff check app tests` | Passed |
| Backend `pytest tests -q -m 'not integration' --cov=app` | 353 passed, 9 credentialed tests deselected; 91.56% coverage against unchanged 87.815587% gate |
| Backend sdist and wheel, `python -m build --no-isolation` | Passed using installed build dependencies; isolated bootstrap could not reach package index |
| Frontend `npm test` | 14 passed |
| Frontend `npm run check` | ESLint, TypeScript and Next production build passed |
| Browser, synthetic HTTP fixture | Full hotspot → opportunity approval → title/cover → Book → approved Bible → Brief → Chapter path; first chapter held for editor, constrained revision created v2, old v1 was read-only, v2 approved/final-locked, and generation disabled after lock. Second chapter passed automatically, then reject v1 → regenerate v2 retained the rejected v1. |
| Responsive browser | Desktop 1428×900 and mobile 390×844 had no horizontal overflow; mobile action buttons remained reachable and at least 44 px high. |

After the Critic provenance follow-up, the full backend suite ran again: **354 passed, 9 credentialed tests deselected, 91.50% coverage** above the unchanged gate. The ZEN-41 targeted suite passed 5 tests, including a rewrite history check that the report's source reference points to v1 while v2 has its own verifier. Frontend lint, types, production build and all 14 tests passed after the UI provenance note. The earlier browser screenshots cover the pass path; they do not demonstrate this new rewrite note.

Desktop evidence: [review and final lock](assets/zen41-review-desktop.png). Mobile evidence: [reachable review controls](assets/zen41-review-mobile-actions.png). These are synthetic data from the local fixture, not real Feishu or model output.

## Verified facts, judgment and open limits

**Verified facts:** The tests and local browser paths above passed. Current upstream PR #36 is open, draft, and based on PR #35; its head when this report was prepared was `fbd3a666485a906472a3457ad96dbf953849b7ff`. The ZEN-41 issue was open/Todo with no explicit Linear blocker relation.

**Engineering judgment:** The API keeps the exact version contract at the server boundary, where a stale or duplicate browser action can otherwise mutate the wrong chapter. The first-N and dimension threshold policy gives a selective human gate while allowing routine passes to proceed.

**Unverified assumptions:** Production Feishu tables have or will receive the additive RevisionTasks fields and sufficient read/write scopes. Real model quality, production pricing/latency and Bitable field limits have not been validated by the synthetic fixture.

**Risks and next actions:** Keep the PR draft while stacked dependencies and live Feishu acceptance remain. Check the PR's own exact-head CI and all review sources after pushing; address any valid findings on this branch. Configure the documented policy values and validate one gated plus one routine run against production credentials before readiness for merge.

## Reusable skill assessment

The `issue-pr-delivery` workflow remains suitable: exact issue/PR mapping, immediate dependency base, commit-specific CI and a durable acceptance report prevented a passing descendant from being mistaken for an accepted production feature. No skill text change was required for this issue.

## Follow-up: truthful Critic provenance after a rewrite

The original Critic scores evaluate the first verified draft, not the rewritten prose. Upstream PR #36 now links the report to that first version even when a rewrite follows. This desk labels a rewritten version's carried report as the earlier draft's evaluation and calls out that the selected rewrite still needs editorial judgment; deterministic checks verify hard rules only. The downstream branch merges that upstream fix so the historical initial version can show its actual report. The ZEN-40 targeted and full backend suites passed after the fix (13 and 349 tests respectively, 91.64% coverage); this desk's checks and exact-head CI are recorded in the PR after pushing.

The approved version now disables the Reject action because the exact server command rejects a conflicting second decision. Revision and final lock remain available. This removes a visible control that could only return a 409 conflict.

## Follow-up: exact RevisionTask replay target

The first replay path checked the editor and constraints but did not recheck the source run, Artifact ID or version number supplied by the caller. It could return an existing revision run to a request naming inconsistent source evidence. The replay path now verifies the persisted source ChapterVersion's book, chapter, run, version and Artifact against the command and task before returning the frozen request. The original exact replay remains idempotent; changed run, Artifact or version values fail closed.

The five targeted chapter review tests pass, including the new mismatch assertions. The full offline backend suite passes with **354 tests, 9 credentialed integration tests deselected and 91.50% coverage** against the unchanged 87.815587% gate. This local environment has no Ruff executable; the PR's exact-head CI must supply the lint result after pushing. No browser behavior changed. This follow-up remains within PR #37 and does not change the live Feishu acceptance limits above.

## Follow-up: version history evidence provenance

The version-history read path previously verified a linked report's Artifact type but did not verify that the Critic report belonged to the same chapter run and source context. A corrupted or incorrectly mapped Base projection could therefore display another run's Critic evidence beside the current prose. The endpoint now checks each projected ChapterVersion's immutable version/run identity, rejects duplicate Artifact projections, and verifies the report's run, chapter, snapshot/brief references and scored source version. A normal rewrite may still carry the initial draft's report when both versions belong to the same run; the UI's earlier-draft notice remains truthful.

A regression replaces a newer version's report with the older run's report, then duplicates the older Artifact projection; both cases now raise an ambiguous-write error instead of returning misleading evidence. The five focused review tests pass. The full offline backend suite passes with **354 tests, 9 credentialed tests deselected and 91.54% coverage** above the unchanged gate. The production Base schema and live identity checks remain open; exact-head CI is required after pushing this follow-up. No frontend interaction changed, so earlier browser evidence remains limited to the original synthetic flow.

## Follow-up: truthful revision run status

The desk previously rendered only RevisionTask `queued`, a durable marker that enqueue succeeded. It remained `queued` after the linked chapter run completed, so the page could imply work was still waiting. The review endpoint now adds a derived `run_status` from the linked WorkflowRun without mutating the task's recovery marker. The desk shows the source version and actual run state. A regression checks the pending and completed states while the persisted task remains `queued`.

Five focused backend review tests passed. The full offline backend suite passed with **354 tests, 9 credentialed tests deselected and 91.55% coverage** against the unchanged gate. Frontend ESLint, TypeScript, production build and all 14 tests passed. The code head `566ac7c8a05007da7304aca56f3b74ea082f8b1a` passed [CI run 36532930148](https://github.com/autism-ip/novelops-agent-harness/actions/runs/36532930148), including the aggregate quality gate. Live Feishu and model limits remain as documented above.

### Browser acceptance after the status change

With the loopback-only synthetic HTTP fixture, a desktop browser followed hotspot collection → analysis → opportunity approval → title and cover selection → book bootstrap → StoryBible approval → chapter brief → first-chapter review. A constrained revision from v1 created v2; the new run first showed `Revision tasks: v1 → run awaiting_approval`. Approving v2 completed the run and changed the label to `Revision tasks: v1 → run completed`, while v1 remained in the version history. This verified the displayed status against a real local API response rather than a static mockup.

The completed label appeared on desktop at 1440 px and phone at 390×844 px. The phone document width equaled the viewport width, the relevant review buttons measured 44 px high, and no Next.js error overlay appeared. Evidence: [desktop revision status](assets/zen41-revision-status-desktop.png) and [mobile revision status](assets/zen41-revision-status-mobile.png). Browser TaskSpace 16 and both local servers were closed after capture. This remains synthetic browser acceptance, not live Feishu or production model validation.

## 2026-09-30 live RevisionTasks schema acceptance

The authorized synthetic Feishu Base received a `RevisionTasks` table with all 18 fields from `FIELD_MAPS["revision_tasks"]`; `chapter_no` is numeric and the remaining fields are text. The backend app identity listed the table through Bitable v1, then production `FeishuClient`, `BaseRepository` and `FeishuStorageProvider` created a synthetic task, read back its integer chapter number and constraint fields, partially updated its status, and deleted it. The companion ChapterVersions table also received its 18 additive fields and passed the same backend-app CRUD and prose readback probe. Both probe records were removed. This verifies schema presence, scope and field transport in the test Base; it does not exercise the full chapter review workflow.

A first full DeepSeek/Feishu chapter attempt reached an eligible brief and a persisted Writer draft but stopped at deterministic verification because the model copied nested planning IDs. ZEN-40 PR #36 records the failure and exact-ID prompt fix. This desk remains draft while a second full run tests constrained revision, selective approval and final lock. The Base link and sanitized outcomes are shared with the user's authorization; no credential or synthetic chapter prose is included.

## Follow-up: full review acceptance remains open after Feishu outage

The authorized RevisionTasks and ChapterVersions schema/CRUD probes above remain valid. Two later full DeepSeek/Feishu attempts did not reach this desk: one stopped at a transient Feishu `1255001 InternalError` before chapter-run creation, and the next stopped during StoryBible work amid GET timeouts and intermittent DNS failures. ZEN-105 PR #23 now has bounded GET-only retries for both observed read faults, without replaying writes; both probes' synthetic rows were cleaned. An independent read shows zero workflow, approval, trace, Artifact, ChapterVersion and RevisionTask rows in the test Base, with only its preexisting retained Book and StoryState.

The downstream branch passes **372 offline backend tests**, with 9 credentialed tests deselected and approximately **91%** coverage; the exact-head CI must be checked after this report commit. The synthetic browser path still demonstrates constrained revision, selective approval and final lock, and the Base's RevisionTasks transport is real. A full production-service revision and final-lock path against live Feishu and DeepSeek remains unverified, so PR #37 stays draft. The next acceptance run should collect a completed revised ChapterVersion, ApprovalEvent, final lock and cleanup when Feishu access is stable.


## 2026-09-30 live review acceptance disposition

The current-code DeepSeek plus Feishu probe completed the upstream first-chapter Writer, verifier, Critic, Rewrite and final verifier, leaving two immutable ChapterVersions and an `awaiting_approval` gate. It then stopped before creating a RevisionTask because the **probe script** treated `review_state.versions` as flat records. The product API returns nested `record` entries as implemented and covered by the review desk tests. The script was corrected; the run's synthetic records were fully cleaned.

The corrected probe's next attempt reached Writer and passed `verify_writer`, but a DeepSeek Critic response failed its strict schema under the probe's zero-retry route. The harness safely stopped it and cleanup succeeded. A third attempt stopped earlier when the Feishu token hostname could not resolve. After DNS recovered, cleanup targeted the current synthetic Book ID from the local journal and succeeded. An independent backend-app read confirmed 1 preexisting Book and 1 StoryState, with zero Artifacts, Traces, PipelineRuns, StepRuns, ApprovalEvents, ChapterVersions and RevisionTasks.

At this stage, the runs strengthened ZEN-40's live evidence but had not exercised a persisted ZEN-41 RevisionTask, second chapter run, exact-version approval or final lock. PR #37 remained draft pending the editorial acceptance recorded below.

## 2026-09-30 real Feishu editorial acceptance

The current PR branch completed a full ZEN-41 editorial path against the authorized synthetic [Feishu test Base](https://fcnaul7kb1kf.feishu.cn/base/T8I6buCMoaiLB6srVBrc9i2jnph) using the backend app identity, production `FeishuClient`/repository/storage/Harness and the actual FastAPI review routes. Model responses in **this** run were deterministic fixtures; no DeepSeek request was made. ZEN-40's separate report records a real DeepSeek Writer → Critic → Rewrite → final-verifier run.

| Check | Observed result |
| --- | --- |
| Story setup | StoryBible approved into StoryState v2; ChapterBrief eligible |
| First chapter | Writer, source verifier, Critic and final verifier passed; first-N policy held v1 at `awaiting_approval` despite a Critic `pass` |
| Review API guard | Unauthenticated `GET /review` returned 401; authenticated read returned exact current version and gate |
| Constrained revision | `POST /review/revision` returned 201 and persisted one `queued` RevisionTask with `must_keep`, nonempty `must_change`, `do_not_change`, source version and new run ID |
| Revised chapter | Rewrite route, verifier and Critic passed; v2's `source_version_id` matched v1; the task's derived `run_status` was `awaiting_approval` |
| Approval and lock | Exact-version `POST /review/decision` returned `approved` and completed the run; `POST /final-lock` returned `final`, repeated identically with the same result; version history remained v2 `final`, v1 `review` |
| Cleanup | Deleted this probe's 4 ApprovalEvents, 21 Traces, 15 StepRuns, 1 RevisionTask, 2 ChapterVersions, 4 PipelineRuns, 2 StoryStates, 18 Artifacts and 1 Book. An independent app-identity read found only the Base's preexisting 1 Book and 1 StoryState; all seven other tested collections were empty. |

The complete run including cleanup took **2,937.25 seconds**. Model fixtures contributed only milliseconds of latency, so this is a material Feishu/Harness performance and deployment risk for continuous editing; no production latency target has been established. A local replay of the same path through the repository's stateful Feishu HTTP fixture counted **1,346 requests**: 1,103 GET, 69 POST, 106 PUT and 68 DELETE; 1,090 requests occurred before cleanup. GETs targeted PipelineRuns 311 times, Artifacts 232, StepRuns 230 and Traces 112. This fixture count demonstrates code-level read amplification, not the exact live request count or per-request latency. Optimize and measure the storage/Harness read path before continuous editorial rollout. The test does not prove DeepSeek can satisfy a human revision constraint reliably, production Base ACL/schema, configured model price accuracy or high-concurrency safety. Earlier local browser acceptance verifies desktop/phone editorial controls and a routine automatic pass, while this run verifies the first-N human gate and HTTP/storage path. Together they support human code review of PR #37; enabling the feature in production should wait for production Base checks and latency profiling.

**Verified facts:** the HTTP status and domain assertions above, retained v1/v2 history, successful cleanup, independent baseline read, earlier offline/backend/browser tests and the separate ZEN-40 DeepSeek loop. **Engineering judgment:** PR #37 is ready for human review as a stacked, disabled-by-default feature. **Unverified assumptions:** production-scale response time, repeated real-model revision quality and production ACL. **Risk response:** keep the feature flags off until those checks pass; preserve one writer and exact-request replay. The existing `issue-pr-delivery` Skill covers the repeatable issue/PR/review workflow. This Base-specific probe is project acceptance evidence and does not justify a new general Skill.


## 2026-09-30 automated review remediation

The automated review of commit `b7a30cba` opened five actionable P2 threads. They are addressed on this issue's PR branch:

| Finding | Change and regression |
| --- | --- |
| Low Critic score bypassed the human gate when the Critic rejected or rewrites were disabled | A configured first-N or score gate now carries the deterministically verified original candidate through final verification to `awaiting_approval`. With neither gate configured, the original terminal failure behavior remains. Parameterized reject and zero-rewrite cases assert the exact gate and retained version. |
| Review desk expanded every historical run | `review_state` expands only the latest run; all historical ChapterVersions still receive provenance checks. A two-run regression asserts only the current run is expanded. |
| Revision replay trusted a mutable frozen JSON column | Replay validates the parsed `ChapterRequest` against Book, chapter, source version, constraints and the task's derived run ID before enqueue. Tests corrupt each field and reject replay before any cross-target work. |
| Chapter switch retained old editor form state | The desk is keyed by Book and chapter, remounting its local version selection, note, constraints and error state when either changes. Frontend lint, typecheck and production build pass. |
| Human gate could close before revision intent existed | The `open` RevisionTask and frozen request now persist before `kernel.decide`. Exact replay reconciles interruption before the gate decision, before enqueue and after the `queued` marker commits; an open intent blocks conflicting generation, approval and final lock. Fault-injection tests cover these stages. |

The focused chapter-review suite passes **12 tests**. The full offline backend suite passes **379 tests**, with 9 credentialed tests deselected and **90.93%** coverage against the unchanged 87.815587% gate. Frontend `npm test` passes 14 tests and `npm run check` passes lint, TypeScript and production build. Ruff is unavailable in this local Python environment; exact-head CI must supply that lint result. A same-path stateful Feishu HTTP fixture replay still passes and counts **1,333 requests** versus 1,346 before this fix, including cleanup. This two-run result verifies functional compatibility and a small request reduction; it does **not** resolve the roughly 49-minute live latency risk. The current-code live and browser reruns are recorded below. The 1,333-request fixture count does not establish a production latency improvement.


## 2026-10-01 exact-head remediation acceptance

**Verified facts.** Commit `0f78e4781af997bbc8db708857d1a198f3bf26b8` passed [CI run 36725983014](https://github.com/autism-ip/novelops-agent-harness/actions/runs/36725983014) and the parallel check run 36725991238: backend lint, frontend lint/types/build, public OpenCLI adapter contract, workflow lint, ZEN-28 behavior contract and aggregate quality gate. Locally, 379 offline backend tests passed with 9 credentialed tests deselected and 90.93% coverage versus the unchanged 87.815587% gate; the 12 focused chapter-review tests, 14 frontend tests and frontend check also passed. The five automated P2 review findings and regressions are itemized immediately above.

The authorized [synthetic Feishu test Base](https://fcnaul7kb1kf.feishu.cn/base/T8I6buCMoaiLB6srVBrc9i2jnph) passed a new current-code run using the production Feishu client/repository/storage and actual FastAPI editorial routes. The model responses in **this** run were deterministic fixtures. StoryBible and ChapterBrief completed; the first chapter stopped at the configured human gate; the API persisted an exact constrained RevisionTask; the second chapter run retained v1 and produced v2; exact-version approval completed that run; final lock succeeded and replayed idempotently. The result file records `status=passed`, v2 `final`, v1 `review`, and `final_locked=true`. Cleanup deleted this run's 4 ApprovalEvents, 21 Traces, 15 StepRuns, 1 RevisionTask, 2 ChapterVersions, 4 PipelineRuns, 2 StoryStates, 18 Artifacts and 1 Book. A separate app-identity read after cleanup found the retained 1 Book and 1 StoryState, with all seven other tested collections empty. The run took **2,677 seconds**, including cleanup.

A fresh local browser run followed synthetic hotspot collection → opportunity approval → title/cover selection → book bootstrap → StoryBible approval → ChapterBrief → chapter review. In chapter 1, an unsent `Must change` value was entered; switching to chapter 2 removed the first chapter's review desk, and switching back to chapter 1 showed the `Must change` field empty. The browser TaskSpace and both fixture servers were closed afterward. This verifies that the chapter-keyed component resets unsent form state on a chapter change. It does not verify a real model's ability to meet the revision instruction.

**Engineering judgment.** The five P2 fixes remove the identified gate, replay, state and UI defects, and the PR is suitable for human code review as a stacked feature that remains disabled by default. **Unverified assumptions and limits.** Production Base ACL/schema, repeated DeepSeek revision quality, configured pricing and concurrent editing remain untested. The 44.6-minute synthetic-model live path confirms that Feishu/Harness read amplification remains a significant continuous-edit latency risk; the 1,333-call fixture replay is an attribution aid, not proof of a meaningful improvement in live throughput. Keep the feature flags off until production checks and latency profiling pass. **Skill assessment.** The existing `issue-pr-delivery` Skill covers this repeatable issue/PR/verification flow; the Base probe is project-specific, so no new Skill was created.

## 2026-10-01 upstream ZEN-40 review sync

This branch merged ZEN-40's four review corrections from commit `15d545f0`: lightweight latest chapter read, fail-closed ChapterVersion Artifact/projection reconciliation, stale-draft labeling and explicit Critic score polarity. The merge conflict was confined to the chapter frontend: ZEN-41 uses the full editorial desk instead of ZEN-40's compact chapter card. The resolved page keeps that desk and the final-lock guard, uses `/generation/latest` for its parent generation controls, adds manual refresh, and displays the backend's stale `current: false` warning in the desk. Both latest-run and full desk polling now stop when the run is terminal or awaiting an editor decision; command responses and manual refresh trigger a new read.

The merged offline backend suite passed **382 tests**, with 9 credentialed tests deselected and **90.93%** statement coverage above the unchanged 87.815587% gate. Frontend passed **14 tests**, ESLint, TypeScript and production build. Local Ruff remains unavailable; this merge's exact-head CI must verify it. The earlier current-code live Feishu run and browser approval/form-state acceptance belong to the preceding ZEN-41 commit, while ZEN-40's separate browser run verifies the new latest endpoint and stale warning in its own panel. The merged ZEN-41 UI logic has been built and tested locally; a new full live Feishu run is unnecessary to establish the frontend integration, and the prior 44.6-minute latency limitation remains.

**Verified:** merged local gates, API regression and the prior issue-specific live/browser evidence with their commit scope. **Engineering judgment:** the stack remains ready for human code review after this merge's CI and review check. **Unverified:** production ACL, latency target and repeated real-model revision quality. The existing `issue-pr-delivery` Skill remains sufficient for this issue/PR synchronization.

### Review sync and exact-code CI closeout

All four newly opened ZEN-40 review threads were answered and resolved on PR #36, and the upstream report-only closeout was merged into this branch. The ZEN-41 merged code commit `b653886973622880517d8f530da448106065d43d` passed both [CI run 36753047269](https://github.com/autism-ip/novelops-agent-harness/actions/runs/36753047269) and [run 36753037914](https://github.com/autism-ip/novelops-agent-harness/actions/runs/36753037914): all listed lint, frontend build, behavior contract and aggregate quality gate jobs succeeded. The earlier five ZEN-41 review threads also remain resolved. This follow-up changes reports only.

## Request-scoped review artifact reuse — 2026-10-08

The read profile separates generation, revision enqueue, review, approval and final lock. The review response loaded the same immutable chapter context, selected version, Critic report and verifier repeatedly. Only `review_state` now shares already integrity-checked payloads within its single read response. Public refreshes and all mutation/decision paths start with fresh remote reads; no shared or persistent cache was introduced. Historical projection/provenance checks remain intact.

The same actual HTTP client/stateful Feishu fixture profile before/after shows v1 review **31→27 GETs** (12.9% fewer) and v2 review **35→31 GETs** (11.4% fewer). Generation, revision enqueue, approval and lock counts are unchanged. A behavior test with a Critic-requested rewrite verifies both historical versions and the report's original draft identity while each shared Artifact is read once. A remote payload tamper after the first response causes the next refresh and approval to fail; no approval event is written, and restoring the remote payload makes the next refresh succeed.

Merged final branch verification: **424 offline backend tests passed**, 9 credentialed tests deselected, **90.07% combined branch-aware coverage** (4,184 statements / 1,094 branches). **58 frontend tests**, lint, types, production build and Ruff 0.16.9 pass. All-source frontend percentages remain 57.99% statements / 61.82% lines / 50.67% functions / 51.92% branches; frontend sources did not change in this correction. A separate ZEN-39 correction limits eligibility expansion to the newest brief, measured at **22→8 GETs with three versions**, and is propagated through ZEN-40 into this branch.

These are measured controlled request counts. They do not prove the historical 44.6-minute live editorial path now meets an editor latency target. Harness transitions, source validation, production schema/ACL and full requirement-event revalidation remain outstanding. Project-wide 100% coverage is not achieved.

## Current real Base read and UI timeout correction — 2026-10-08

Backend code `fb2c111ab861cdefdb3f83d288ffc4da15e8de53` passed a focused live read against the user-authorized synthetic Base using the actual Feishu client, repositories, storage provider and mounted FastAPI review endpoint. The existing stateful workflow fixtures first generated a complete synthetic Book, StoryState, eligible brief and reviewed chapter locally; only the 21 required synthetic rows were transferred after every target business key was confirmed absent. No existing row was overwritten. This was read acceptance of pre-existing synthetic workflow output, not live chapter generation or a model-quality test.

The unauthenticated review request returned 401. The authenticated response returned 200 and matched the exact selected chapter, Bible, brief, context snapshot, verifier and version history; it reported two stored model attempts. **27 actual Feishu GET requests took 65.460 seconds**. Setup took 209.034 seconds; cleanup took 197.543 seconds with no failures. A new independent app-identity client found **zero remaining probe rows**. Total pytest wall time including independent cleanup was 553.63 seconds. There were no real model calls. The approved [test Base](https://fcnaul7kb1kf.feishu.cn/base/T8I6buCMoaiLB6srVBrc9i2jnph) and results are shared under the user's explicit authorization.

This exposed a user-visible mismatch: the browser client aborted reads at 10 seconds while the valid review response took over one minute. Code `4bc60bb12fd7ef409d0f297219237bd77ed29259` gives only the chapter review GET a **120-second bounded read deadline**, keeps the other browser requests at their existing default, and shows a short loading expectation. The Next.js proxy declares `maxDuration=120`; the production build's functions-config manifest contains that value. Deployment platform limits still need validation. This permits a slow valid response to finish; it does not resolve the remaining storage latency.

Two new tests render the actual ChapterReviewDesk, resource hook and HTTP client with a controlled transport. Before the fix, a 65.46-second response aborted at 10 seconds and never showed prose. Afterward, prose renders once, terminal polling stops, and timers clear. A hung read still aborts at 120 seconds and exposes recovery guidance. These are fake-clock behavior tests, not a new live browser or deployed-proxy run. A separate HTTP test covers stale revision rejection, exact constrained RevisionTask creation/replay, v2 review, approval and final lock with the immutable v1 retained.

Final code-tree gates: **425 offline backend tests passed**, 9 credentialed tests deselected, Ruff passed; **60 frontend tests**, ESLint, TypeScript and production build passed. Backend statements/lines **92.83% (3,884/4,184)**, branches **79.98% (875/1,094)**, combined **90.17%**; 300 lines, 219 branch arcs and 193 partial branch lines remain. Python named-function entry measurement is **95.77% (385/402)** with 11 anonymous lambdas outside that metric; it is not full function coverage. The raw definition count includes six Protocol method declarations. Coverage.py's inherited defaults omit those declarations and four adjacent blank lines; no project exclusion was added.

All-source frontend coverage: **58.17% statements (587/1,009), 62.03% lines (531/856), 51.01% functions (151/296), 53.43% branches (599/1,121)**. The HTTP client, resource hook and previously verified auth/proxy/parser modules retain all four metrics at 100%. No ignore or gate change was made. The project-wide 100% requirement, full current-head event revalidation, continuous editor latency and production rollout acceptance remain open. All 13 Linear issues remain In Review; no Done or merge approval is implied.

## Native batch consumption (2026-10-09)

The response collects current manifest/history Artifact IDs and reads their
integrity-checked payloads in one batch, loaded lazily inside the existing domain
error boundary. Present payloads and confirmed absence are reused only for this
response. Version rows are read once for response assembly; canonical Book/State,
brief eligibility, latest run and final-lock checks remain in force. RevisionTask
run statuses are queried as one business-key batch. Decisions and subsequent
refreshes still start with fresh reads; no shared or persistent cache was added.

The same complete HTTP-transport editorial fixture measured:

| Event | Before batch consumption | After |
| --- | ---: | ---: |
| Generate v1 | 354 | 354 |
| Read review v1 | 27 | 22 |
| Request editorial revision | 94 | 94 |
| Generate v2 | 251 | 251 |
| Read review v2 | 31 | 23 |
| Approve v2 | 30 | 30 |
| Lock final | 26 | 26 |

These are request counts against the actual application/client/repositories and
stateful HTTP fixture, not live latency. The fixture verified immutable v1/v2
history, explicit RevisionTask constraints, exact approval and final lock. A
regression enforces <=23 read requests for a two-version rewrite desk, requires a
multi-ID Artifact search and counts each shared source/verifier ID exactly once.
New cases verify required Artifact deletion fails closed, restored data is read
fresh, a pending chapter's optional Critic absence is queried once, and an
unstarted chapter returns empty history without fetching Artifacts. Existing
remote-tamper refresh/decision assertions and provenance validation are preserved.

Local verification: **481 backend tests passed**, **10 opt-in live cases
deselected**, Ruff passed. Full-source backend statement/line coverage is
**3,952/4,251 = 92.97%**, branch **906/1,124 = 80.60%**, combined **90.38%**;
192 branch lines are partially covered. Function coverage for this new head is
not established. **60 frontend tests passed**, lint/types/production build passed.
Full-source V8: statement **58.17%**, line **62.03%**, function **51.01%**, branch
**53.43%**. No exclusions, skipped offline tests or relaxed thresholds were added.
The whole-project 100% objective therefore remains open.

The fresh application-identity live probe passed **1/1 in 279.25 seconds** at
code `404cd7cdee01833bec608a3a190c4bc33611872c` in the authorized synthetic Base.
It seeded **21 rows** after absence checks and read the mounted authenticated
review API: chapter, Bible, brief, snapshot, verifier, history and two model-attempt
usage records matched their expected immutable sources. Unauthorized access was
rejected. The response took **26.703 seconds / 22 read requests** (11 GETs and 11
native search POSTs); no mutation request occurred during the read. Seed time was
121.270s and cleanup 103.156s, with no cleanup failure. An independent app client
found **zero remaining probe rows**. No real model was called.

The prior equivalent persisted case took 65.460s / 27 GETs. These are two single
observations on different runs; network/service variation prevents attributing the
entire latency difference to code or claiming p95 performance. The controlled
same-transport count comparison above isolates the batching change. This verifies
the actual Feishu read path, not live model generation, current frontend write
latency, a deployed proxy, platform duration limits or continuous-editor acceptance.


## Slow editorial actions and exact empty-note replay — 2026-10-09

**Actual requirement events and discovered defects.** The mounted API with real
app-identity Feishu storage approved an exact ChapterVersion and then final-locked
it. Approval took **34.463s / 30 requests**, final lock **25.398s / 26 requests**;
this established that the browser's default ten-second POST budget was too short.
The 21 transferred synthetic rows plus one ApprovalEvent were deleted; independent
reads found zero remaining IDs. This probe did not call a real model.

A subsequent current-client/production-Next-proxy run accepted the approval in
37.841s but rejected the identical replay with 409. A focused one-row real Base
probe established the cause: the create response contains `reason=""`, whereas
native search omits that empty text field; every other event field round-tripped
unchanged. That row was independently confirmed absent after cleanup. Chapter
review now treats only an omitted optional note as the empty domain default.
Version, target, Artifact, action, editor and non-empty notes still compare exactly.
Approve and reject regressions assert a single event, zero mutation on replay and
rejection of changed notes/editors/actions. Source commit:
`3241108810e3a26494d8b71fd1d5e0a647e6529e`.

**User-visible implementation and tests.** Chapter review GET and all four exact
editorial POST actions use a 120-second bounded client deadline. Other requests
retain ten seconds. The client keeps the timer until complete JSON body parsing,
and an AbortError from an error body remains a timeout rather than a fabricated
502. Saving has its own progress message; an expired deadline retains the exact
command for explicit replay. Real component/resource/client tests verify a
34.463-second response, no duplicate submission, all four actions, 120-second
expiry, byte-identical replay and timer cleanup. Additional behavior checks cover
stale drafts, final-lock read-only state with old prose still readable, earlier
Critic provenance, legacy-only history, empty/running chapters, expired sessions
and failure to persist recovery intent before any write.

**Local verification and full-source coverage.** `BACKEND_API_KEY=ci-contract-key
python -m pytest -p tests.function_entry_coverage -m 'not integration' --cov=app
--cov-branch` passed **483 tests**, with 10 explicit live cases deselected; Ruff
0.16.9 passed. Backend statements/lines **3,953/4,251 = 92.99%**, branches
**907/1,124 = 80.69%**, combined **90.42%**. The complete source-function entry
probe reports **401/419 = 95.70%**, including **11/11 lambdas**. Its raw denominator
also retains the seven Protocol declarations; no calls were manufactured for
empty declarations. Module/class execution and compiler-generated comprehensions
are not source functions. The plugin was validated against decorated/nested
functions, methods, distinct same-line lambdas and a retained uncalled function.
The reproducible plugin is `backend/tests/function_entry_coverage.py`; its result
is `docs/reports/2026-10-09-function-entry-coverage.json`. Only its generated JSON
output is git-ignored, not application code or coverage responsibility.

`npm --prefix frontend run test:coverage` passed **77 tests**; lint, typecheck and
production build passed. All-source V8 coverage is **596/1,011 = 58.95% statements**,
**537/857 = 62.66% lines**, **155/296 = 52.36% functions**, and **627/1,127 = 55.63%
branches**. The HTTP client retains all four metrics at 100%. No test removal,
new app exclusion, threshold change or offline skip was used. Whole-project 100%
remains unfinished.

**Probe failure handling and reusable workflow.** The first production-proxy
probe collided with a concurrent `.next` build and did not send an approval. Its
cleanup then failed while terminating an already-exited child. Recovery removed
19 stable records plus two random Trace IDs, validated by their exact owned run,
Writer/Critic routes and step identities. Independent reads verified no remaining
records or model traces for that run. A reconstructed fixture's new random Trace
IDs were not accepted as proof of cleanup. The probe now starts an immutable build
copy before seeding, journals actual attempted IDs, tolerates exited children and
runs independent verification within finally. The later replay-409 run cleaned
all 22 rows and independently verified zero residual IDs despite its failure.
The existing `issue-pr-delivery` skill was updated with operation-based read/write
fault injection and exact-ID/finally cleanup rules, then validated by skill-creator.
No additional personal skill was created.


### Current production-proxy requirement event and cleanup reconciliation

Source tree `3241108810e3a26494d8b71fd1d5e0a647e6529e` completed the current
TypeScript ApiClient (transpiled for this probe) → local production Next.js signed
session proxy → Uvicorn FastAPI → actual Feishu path. The probe starts no worker;
its synthetic v1 was generated locally beforehand. It is not a deployed-host or
browser-DOM test. Before each signed action, an unsigned POST returned **401**;
no client-side backend API key was supplied. Each signed action sent exactly one
client POST and returned the exact version/Artifact/operator expected:

| Event | Client elapsed | Feishu requests | Persisted result |
| --- | ---: | ---: | --- |
| Approve exact v1 | 30.259s | 30 | Exactly one matching ApprovalEvent; version approved |
| Replay byte-identical approval | 22.824s | 27 | Same event; all 27 calls read-only, zero new writes |
| Lock that same v1 | 24.487s | 26 | Version final with the exact locking editor |

The authenticated mounted desk read also matched all immutable sources/history
in **25.732s / 22 reads**. These are single observations, not latency targets or
p95 benchmarks. All three operation assertions and the final single-event/final
row checks passed. The overall pytest nevertheless **failed during cleanup**:
one PipelineRun cleanup call raised FeishuAPIError (its code was not captured).
This failure is retained in the runtime report, not rewritten as a passing run.
A separate recovery read all **22 original journal IDs**, found no remaining rows
and sent **zero further deletes**. A fresh independent app client batch-read all
collections and verified **zero residual rows**; that recovery test passed **1/1
in 25.29s**. The owned proxy/backend processes and build copy were removed.

`docs/reports/2026-10-09-editorial-runtime.json` preserves both the completed
requirement events and failed initial cleanup/reconciliation. This closes the
current routine approval/replay/final-lock path and its client deadline check.
Full live generation, constrained rewrite and selective human gates at the latest
code, repeated DeepSeek quality/cost, complete browser acceptance and production
platform/ACL/latency remain pending. The source and report PR heads still require
fresh CI/review audits. No issue is marked Done or safe to merge under the 100%
coverage requirement.


### CI timing remediation and required Node version

Both runs for report head `f46f7ae3040fe4c55e2be879bca9ad6a0fbaaa5c` failed
four final zero-timer assertions; the other 73 frontend cases and all backend,
adapter and workflow gates passed. The first test-only remediation awaited the
refresh body, but `e12da435c793d61265cef14fa99dae696eec6892` still failed those four
assertions in CI. Local Node 25 success did not establish the required Node 24 gate.

The bundled **Node 24.19.0** reproduced the failure locally. Temporary timer
inspection identified jsdom's bound `_dispatchStorageEvent` from the successful
`sessionStorage.removeItem`: a zero-delay event queued for the next fake-clock
turn. The final test waits for the real refresh body and advances that next event
turn by 1ms before asserting zero timers. Every exact-command, single-write,
120-second deadline, recovery and zero-timer assertion is retained; no application
code, test count or coverage threshold changed. Debug instrumentation was removed.

Using the repository-required Node 24, **77 frontend cases**, all-source coverage,
ESLint, typecheck and production build pass. Reported coverage is unchanged. The
application still matches source commit `3241108810e3a26494d8b71fd1d5e0a647e6529e`;
its actual Feishu event evidence is unaffected. Both failed CI heads remain
historical evidence. The final test/report head requires fresh GitHub checks.


## 2026-10-09: projection read reduction and full editorial regression

The owning fix is ZEN-35 PR #29 (`389586c4`): Git history shows that issue introduced projection. Kernel PR #24 has no projector extension, so no new projector capability was added to its scope. The first focused old-behavior test failed on three step-list reads versus the required two for an unprojected one-step tick. Five owning regressions now cover completed output, fresh type selection, cancellation, failed projection repair without repeating the effect, and explicit missing-run failure. The first complete collection exposed five setup errors; fixture reuse was corrected and all original assertions retained.

Every descendant was merged and tested at its own scope with required Node 24.19.0, backend branch coverage, Ruff, frontend tests and lint/types/build: ZEN-36/37 435 backend tests, ZEN-38/107 442, ZEN-39 451, ZEN-40 468 and ZEN-41 488 before the final new round-trip test. Their source validation heads and measurements are in `2026-10-09-projection-read-profile.json`. The final full backend with raw function entry instrumentation passed **489 tests in 167.14s**, 10 live cases deselected; **77 frontend tests**, frontend coverage and Ruff passed.

The current actual client/repository/provider/kernel/ChapterLoop composition with a synthetic HTTP store and deterministic model fixtures passed v1 → immutable constrained RevisionTask → Rewrite/Critic v2 → exact approval → final lock. It preserves v1 prose, source identity, constraints, one task, one approval and successful verification. A durable whole-round-trip read budget regression was added; no persistent business cache was introduced.

A controlled before sample extracts only the exact pre-fix `_project` method from Git in a separate process, keeping all other current code and fixtures unchanged. It matches the historical baseline. The seven stages move from **800 to 790 HTTP calls (1.25%)**: v1 generation 354→349 and v2 generation 251→246; review v1 22, revision creation 94, review v2 23, approve 30 and lock 26 are unchanged. The only differences in operation counters are five fewer `GET step_runs` calls per generation. All mutation counts match. Fixture preparation and an intermediate pending revision read are outside both samples. The controlled old-method override was never loaded into the coverage or repaired-behavior acceptance run.

Current backend statement/line **3,956/4,254 = 92.9948%**, branch **909/1,126 = 80.7282%**, combined **90.4275%**, raw function entries **401/419 = 95.7041%**, lambdas **11/11**. All-source frontend: statement **596/1,011 = 58.95%**, line **537/857 = 62.66%**, function **155/296 = 52.36%**, branch **627/1,127 = 55.63%**. No application exclusion, weakened assertion, skipped applicable test or lowered threshold was added. The 100% objective remains unmet.

Verified facts: fewer unused reads and preserved full synthetic editorial events, every descendant scope gate passed, no external fixture rows created in this turn. Engineering judgment: ten saved calls are a modest improvement and leave the larger Feishu workflow latency risk. Unverified: real Feishu latency after this change, current real-model full generation/rewrite quality, deployed frontend timeout limits, production ACL/schema readiness and whole-project 100%. Initial audit found all 13 PRs open with no unresolved review threads; fresh exact-head CI/review after the final report/test push is still required. Existing issue-pr-delivery workflow is sufficient; no new skill is necessary. Issues remain In Review, with no merge or deployment claim.


## 2026-10-10: exact command recovery through the actual client

ZEN-41 PR #37 now catches storage removal failure from both checked-history buttons. A failed clear keeps the identical pending command, displays the cause and storage recovery guidance; successful retry clears both command and error without writing a chapter decision. Two red cases reproduced uncaught errors before the source change; both are now green.

Added 11 integration contracts using actual ApiClient, resource polling and editor identity (only native HTTP/storage boundaries controlled). All **88 frontend tests** pass; required Node 24.19.0 lint (zero warnings), types and production build pass. Tests cover exact replay with changed editor, 401/409 recovery, no untracked write when storage fails, historical evidence, unavailable legacy metadata, SSR privacy and real polling → selective gate → approval state change. No tests removed, assertions weakened, coverage exclusions added or gates lowered.

| All frontend source | Covered / total | Percent |
| --- | ---: | ---: |
| Statement | 621 / 1,013 | 61.30% |
| Line | 553 / 858 | 64.45% |
| Function | 168 / 295 | 56.94% |
| Branch | 645 / 1,127 | 57.23% |

Review desk line/function metrics reach 100%; its statement is **110/117 (94.01%)** and branch **160/166 (96.38%)**. Editor identity reaches all four 100%. **Whole-project coverage is still below the required 100%.** Defensive handlers were not privately invoked to manufacture execution. Backend source was untouched; previous 489-test result remains separately scoped historical evidence.

Actual production Next → signed-session proxy → FastAPI/kernel/record repositories workflow with synthetic HTTP/model boundaries: keyboard desktop **1280×900** and pointer mobile **390×844** preserve exact intent on clear failure, show contextual recovery guidance, expose a **44px** button and have no horizontal overflow. After restoring storage, the same user action removes command/error. Zero POST and uncaught errors; fresh HTTP GET confirms original v1 remains review with run/gate awaiting approval. This verifies the local recovery requirement event, not model quality or real Feishu latency.

Two CDP screenshot timeouts prevent a new visual inspection claim. Original space/process handles were gone; user authorized a replacement space and local services. A mobile click after metrics change was intercepted; fresh DOM/snapshot inspection located the live button and normal ref click succeeded. A script helper error was repaired without replaying the already executed action. Browser space was closed once. Structured evidence and all limitations: [review recovery report](2026-10-10-review-recovery.json).

Latest pre-push audit: all 13 open PRs have no unresolved threads or changed review/discussion bodies; ZEN-41 remains In Review. Exact-head CI after this delivery is pending until checked independently. Current full real-model flow, deployment/schema/ACL acceptance and project-wide 100% coverage remain open. Existing issue-pr-delivery, TDD, Impeccable and ego-browser skills reused; no new skill warranted. Impeccable detector ran once and returned []; DESIGN.md is newer than its sidecar, which can be refreshed separately with document.


### Recovery source delivery CI

Source/test delivery `ff0f02f082bd9fd214827c9676dfdecee595c8b1` passed both [PR CI 38012514692](https://github.com/autism-ip/novelops-agent-harness/actions/runs/38012514692) and [push CI 38012511074](https://github.com/autism-ip/novelops-agent-harness/actions/runs/38012511074), including every job and aggregate quality gate. This report-only follow-up preserves application/tests; its final head is checked separately in PR #37. No wider acceptance or Done claim follows from CI.
