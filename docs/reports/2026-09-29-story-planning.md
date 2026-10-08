# ZEN-39 — StoryBible and chapter planning delivery

- Linear: [ZEN-39](https://linear.app/zenhungyep/issue/ZEN-39/implement-storybible-and-chapter-planning-workflow)
- GitHub: [Issue #12](https://github.com/autism-ip/novelops-agent-harness/issues/12)
- Delivery: draft [PR #35](https://github.com/autism-ip/novelops-agent-harness/pull/35), branch `codex/zen-39-story-planning`, review base ZEN-107 [PR #34](https://github.com/autism-ip/novelops-agent-harness/pull/34). Merge order follows the PR stack.

## Delivered behavior

The StoryArchitect route now creates a strict, versioned StoryBible artifact from the Book's exact canonical StoryState. Every initial Bible and major direction change stops at a human approval step. Approval names the exact review step, artifact, and output version. The Harness then applies a validated patch to StoryBible, Characters, PowerSystem, and StyleContract, records an immutable next-version StoryState, and advances the Book pointer. Revision feedback carries into the next proposal. A replay after an interrupted pointer update reuses the same artifact and state IDs.

The ChapterPlanner route creates a StoryContextSnapshot with exact state and Bible references, followed by a versioned ChapterBrief. Routine briefs proceed automatically. The eligibility endpoint exposes a brief only when its run completed and its source state is still current; a major Bible change makes the older brief ineligible. The Book page offers the approval and brief controls with exact-version retry after an unknown result, compact preview, full Bible details on demand, provenance, and responsive cards. The workflow contract and recovery behavior are documented in [story-planning.md](../story-planning.md).

Main changes: `backend/app/story_planning.py` owns the domain workflow and artifacts; `backend/app/api/routes/story_planning.py` owns exact-version API commands; `backend/app/books.py` handles evolved-state bootstrap replay; `frontend/src/components/books/story-planning.tsx` and `planning-state.ts` provide the Book controls and retry validation. The design reuses the confirmed B layout and `DESIGN.md` visual tokens.

## Verification and review

| Evidence | Result |
| --- | --- |
| Backend offline suite | 336 passed, 9 credentialed integration tests deselected; 92.15% statement coverage against the unchanged 87.82% gate |
| Frontend | 11 tests passed; ESLint, TypeScript, and Next.js production build passed |
| Ruff | `app` and `tests` passed |
| Backend package | sdist and wheel build checked |
| GitHub CI | [Run 36501006626](https://github.com/autism-ip/novelops-agent-harness/actions/runs/36501006626) for head `7433e07f0d84c433d428411ed3be93f232fbaf07`: all listed jobs and aggregate `CI quality gate` succeeded |
| Desktop browser, 1440×900 | Synthetic hotspot → approved opportunity → title/cover → Book → initial Bible approval → chapter brief → major Bible proposal; major approval control visible at y841–885 in the 900px viewport |
| Phone browser, 390×844 | Major Bible approval and regenerated brief completed through the Book UI; approval control at y540–584 with the planning panel at viewport start; no horizontal overflow |
| Provenance | Chapter 1 brief initially used StoryState v2; major Bible approval advanced to v3, invalidated that brief, and regenerated brief v2 from v3 with an exact snapshot reference |

Backend behavior tests additionally cover stale or invalid Bible output, generic workflow creation bypass, interrupted Book pointer recovery, failed brief regeneration, feature flag dependency, and revision feedback. Browser acceptance used the repository's synthetic HTTP storage and model fixture. Live model quality and production Feishu credentials remain deployment checks.

Post-fix live smoke check (2026-09-30): with the user-configured DeepSeek Flash key, the actual `BIBLE_PROMPT`, `BibleInput`, `BibleContent`, `ModelRouter`, and `ChatProvider` completed one synthetic StoryState request under a `timeout=20`, `max_output_tokens=2048`, `max_retries=0`, `deepseek_thinking=disabled` route. The result passed `BibleContent` schema and its protagonist text retained the canonical age 19. This verifies one production prompt/schema/provider path after the ZEN-106 DeepSeek route fix. It did not create a Book, persist an Artifact, exercise human approval, test chapter briefs, or measure repeated story quality. The same probe's separate chapter-critic call is recorded in ZEN-40's report; combined usage was 1,160 input and 1,819 output tokens with 12.318 seconds model latency, without a provider price estimate.

Review status at the report check: no submitted reviews, discussion comments, or inline threads on PR #35. No review finding needed a code disposition. The PR remains draft while the full live story-planning acceptance is being completed; its base PR #34 is now ready for review.

Screenshots: [desktop major approval](assets/zen-39-storybible-major-desktop.png), [phone major approval](assets/zen-39-storybible-major-mobile.png), [phone regenerated brief](assets/zen-39-chapter-brief-mobile.png).

## Findings, limits, and next dependency

The first Book layout pushed approval controls beyond the initial viewport. A compact premise/protagonist preview and expandable full Bible resolved that in the tested desktop and phone layouts. Story planning workflow statuses no longer disable unrelated hotspot actions. The Book bootstrap replay now accepts the expected later StoryState pointer while preserving the original bootstrap identity.

ZEN-40 chapter generation must consume the policy-eligible ChapterBrief and immutable snapshot boundary. This PR does not claim chapter prose generation or full live Feishu/model acceptance. The existing `issue-pr-delivery` skill remains useful for issue-to-PR tracing; no new reusable skill is warranted from these domain-specific contracts.

The original verification above was scoped to its reported commits. The newer live DeepSeek and Feishu evidence below extends the verified Bible path; ChapterBrief materialization and production configuration remain separate acceptance checks.

## Live DeepSeek and Feishu acceptance — 2026-09-30

The user configured a valid DeepSeek key locally; no credential value was copied into this report. A synthetic Book with a 19-year-old protagonist was bootstrapped through production `BookService`, `HarnessKernel`, `FeishuClient`, `BaseRepository`, `FeishuStorageProvider` and `ArtifactStore` in the authorized test Base. Deterministic in-process fixtures supplied the already approved upstream opportunity/title/cover selection; their production workflows were outside this probe.

`StoryPlanningService.enqueue_bible` persisted a three-step run. The registered `story_bible.generate` handler called the actual `BIBLE_PROMPT` and `BibleContent` schema through `ModelRouter` and `ChatProvider` on `deepseek-flash` with thinking disabled. The generated StoryBible Artifact was persisted and read back. The review step reached `awaiting_approval` at output version 1; an approval naming that exact Artifact created one ApprovalEvent. The commit step produced an immutable StoryState v2, advanced the Book pointer, and the run completed. The final StoryState's `StoryBible.bible_artifact_id` matched the approved Artifact. Total elapsed time including cleanup was 418.57 seconds. Cleanup deleted 1 approval event, 4 trace rows, 3 step rows, 1 pipeline run, 2 StoryStates, 3 Artifacts and 1 Book; no probe IDs were retained.

A separate low-cost `ChapterPlanner` prompt probe used the production `BRIEF_PROMPT`, `BriefInput`, `BriefDraft`, `ModelRouter` and `ChatProvider` with a synthetic StoryContextSnapshot. DeepSeek Flash returned a schema-valid opening hook, scene goal, conflict, payoff and ending hook in 2.21 seconds. This does not establish full-brief story quality or live Feishu materialization; versioned snapshot and brief persistence remain covered by offline integration and synthetic browser acceptance.

The live workflow proves the StoryBible generation, exact approval and StoryState patch path on this test Base. It does not certify production ACL, full upstream selection workflow, long-form quality, rate ceilings or ChapterBrief persistence on live Feishu. Pricing remains unestimated because route price fields were unset. Review/CI status should be rechecked on the eventual report commit. The existing `issue-pr-delivery` skill covers the repeatable workflow; no new skill is justified by this domain-specific probe.

## Follow-up: live ChapterBrief persistence and eligibility

A subsequent synthetic run in the same authorized Base (2026-09-30) repeated real DeepSeek StoryBible generation, exact Artifact approval and StoryState v2 commit, then ran both registered ChapterBrief steps through the production services and backend app identity. `chapter_brief.generate` returned a schema-valid `ChapterBriefDraft`; `chapter_brief.materialize` persisted the versioned `ChapterBrief` and its planning `StoryContextSnapshot`. The run completed, and `eligible_brief(book_id, 1)` returned the exact persisted brief. The downstream ZEN-40 Writer then consumed it, which confirms the stored brief could be read by the next workflow. That Writer's deterministic verification later rejected incorrect model-echoed chapter IDs; ZEN-40 records the failure and fix separately. The brief itself had passed its generation, materialization and eligibility gates before that failure.

The full probe lasted 1,550.97 seconds including cleanup. All its temporary rows were removed: 1 ApprovalEvent, 10 Traces, 10 StepRuns, 3 PipelineRuns, 2 StoryStates, 8 Artifacts and 1 Book. This extends the earlier live Bible evidence to the ChapterBrief persistence path on the synthetic Base. It does not measure repeated brief quality, production ACL or rate ceilings. The local key and source prose are absent from this report.

## Current-brief read amplification — 2026-10-08

Profiling found that `eligible_brief` expanded every historical brief to return only the newest one. A behavior regression using the actual Feishu client/repositories and stateful HTTP fixture reproduced **22 GETs for three versions**. Eligibility now selects the latest persisted run before expanding it: **8 GETs for the same three-version case**, a 63.6% reduction in this fixture. Run definitions are still validated, the current state and latest run still determine eligibility, and an unfinished newest proposal never falls back to an older completed brief. The full history endpoint is unchanged. There is no persistent or cross-request cache and no write-contract change.

On the owning ZEN-39 branch: **393 offline backend tests passed**, 9 credentialed tests deselected; branch-aware coverage **91.52% combined** against the unchanged gate. **49 frontend tests**, lint, types and production build passed; Ruff 0.16.9 passed. This is request-count evidence for controlled storage, not a current production latency measurement. Remaining storage/Harness requests and full live event acceptance still require work. Project-wide 100% coverage remains pending.

## Native search propagation (2026-10-09)

The latest-eligible-brief regression retains its eight-request bound and exact
latest Artifact assertion. It now recognizes native `POST .../records/search`
as read-only and inspects the structured filter values, positively requiring the
latest brief ID and rejecting every older brief ID. This preserves the historical
read-amplification guard across the updated provider transport.
