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
