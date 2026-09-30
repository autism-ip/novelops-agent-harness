# ZEN-40 — Chapter generation, critique and verification delivery

- Linear: [ZEN-40](https://linear.app/zenhungyep/issue/ZEN-40/implement-chapter-generation-critique-rewrite-and-verification-loop)
- GitHub: [Issue #13](https://github.com/autism-ip/novelops-agent-harness/issues/13)
- Delivery: draft [PR #36](https://github.com/autism-ip/novelops-agent-harness/pull/36) on `codex/zen-40-chapter-loop`, based on ZEN-39 [PR #35](https://github.com/autism-ip/novelops-agent-harness/pull/35). Merge in stack order.

## Delivered behavior

An approved StoryBible and policy-eligible ChapterBrief can now drive generation of chapters 1–3 and subsequent chapters. A chapter-specific StoryContextSnapshot freezes exact StoryState, StoryBible, ChapterBrief and planning snapshot references. The Harness runs Writer, deterministic verification, structured Critic, conditional Rewrite and final verification. A Critic pass skips Rewrite; a revise allows one constrained Rewrite by default; a reject or hard-rule failure cannot make a ChapterVersion reviewable. Optional estimated-cost and rewrite limits stop work before further model calls. Model attempts retain route, prompt, token, cost estimate, latency and retry evidence.

Verified prose is materialized as immutable ChapterVersion Artifacts with additive ChapterVersions projection fields. Regeneration uses the next persisted version number, including when a previous run failed after producing a candidate. A human revision names the current review version and explicit constraints. The exact-version final-lock command is idempotent for the same target and operator. Generic workflow creation cannot forge this loop. Legacy ChapterVersions rows remain readable. The Book page adds a responsive chapter panel with generation, current verified prose, structured critique, all version numbers and source/model details; unknown submission outcomes can be retried with the identical command. The full contract is in [chapter-loop.md](../chapter-loop.md).

Main modules: `backend/app/chapter_loop.py` owns the domain loop; `backend/app/api/routes/chapter_loop.py` exposes exact-source commands; `backend/app/feishu/table_map.py` adds projection fields; `frontend/src/components/books/chapter-generation.tsx` and `chapter-state.ts` provide the Book controls. The UI follows the approved top navigation and list/approval split in `DESIGN.md`, with rounded responsive surfaces and subtle existing motion.

## Verification and review

| Evidence | Result |
| --- | --- |
| Backend offline suite | 349 passed, 9 credentialed integration tests deselected; 91.70% statement coverage against the unchanged 87.82% gate |
| Frontend | 12 tests passed; ESLint, TypeScript and Next.js production build passed |
| Ruff | `app` and `tests` passed |
| Backend package | sdist and wheel built successfully |
| GitHub CI | [Run 36515116733](https://github.com/autism-ip/novelops-agent-harness/actions/runs/36515116733) for head `9e0d45fa55821ada9dcab66bf83a612f01e0a845`: every listed job and aggregate `CI quality gate` succeeded |
| Desktop browser, 1428px | Synthetic hotspot → approved opportunity → title/cover → Book → approved StoryBible → eligible ChapterBrief → chapter generation completed with Critic pass and two model calls; chapter and critique columns remained usable |
| Phone browser, 390px | The same Book flow and regeneration controls worked in a stacked layout without horizontal overflow; the primary action was visible near the panel start |
| Regression coverage | Exact refs for chapters 1–3, bounded rewrite/reject/hard failures, critic validation, provider retry, cost cap, final-lock idempotency, revision source constraints, stale state, auth and forged workflow rejection |

During browser acceptance, the running fixture still had an older version allocator that skipped from v1 to v3 after a pass. The allocator was then changed to use the next persisted ChapterVersion number. The updated backend regression confirms v1 then v2; this particular correction was **not** rerun in the browser. Browser evidence supports the responsive flow and model loop, while the backend test supports contiguous numbering.

Screenshots: [desktop chapter and critique](assets/zen-40-chapter-desktop.png), [phone chapter panel](assets/zen-40-chapter-mobile.png).

Review status at the report check: no submitted reviews, discussion comments or inline threads on PR #36. No review finding needed a code disposition. The PR remains draft because PR #35 and its upstream stack remain under review. This CI result belongs to the head named above; the subsequent report-only commit needs its own check.

## Findings, limits and next dependency

The first model input omitted the required snapshot Artifact ID even though the output had to echo it. Supplying the ID to Writer and Rewrite fixed the contract. The first Book panel also showed only the latest run's version subset; it now reads the chapter-wide version history. The persisted version allocator was corrected after the browser run as described above.

**Verified facts:** the local gates, synthetic browser actions, tested source references, version-number regression and package build above. **Engineering judgment:** the code is ready for human review as a stacked draft PR. **Unverified assumptions:** production model quality, live Feishu permissions and new field mapping, Bitable prose size/rate limits, route prices and deployment behavior. **Risks and next actions:** run live integration acceptance when the Feishu bot scope and production credentials are available; ZEN-41 supplies the full editorial review desk and RevisionTask controls on top of these backend commands. A synthetic transport does not establish live acceptance.

The existing `issue-pr-delivery` skill remains useful for one-issue/one-PR tracing, exact-head CI and evidence separation. These chapter-specific rules do not warrant a new reusable skill.

## Follow-up: exact Critic source on rewrite and reject

Reviewing the downstream chapter desk exposed a provenance gap: the CriticReport evaluated the initial verified ChapterVersion, but the projection attached it only to the selected final version. On a rewrite, the initial candidate therefore lacked its own report and the rewritten version appeared to have been scored directly. The Critic step now links its immutable report to the exact source candidate before the rewrite decision. The selected rewritten version retains the report as the reason for rewriting, while its deterministic verifier remains the evidence for the new prose. The report's `source_refs[2]` identifies the version actually scored; the rewritten prose is **not** claimed to have received another Critic pass.

Regression assertions cover a revised run and a rejected run. The targeted chapter suite passed 13 tests; the full offline backend suite passed 349 tests, with 9 credentialed tests deselected and 91.64% statement coverage above the unchanged gate. Ruff passed. This is an implementation follow-up on PR #36; its new exact-head CI and review status must be checked after the push.

## Follow-up: live DeepSeek critic prompt smoke check

On 2026-09-30, the user-configured DeepSeek Flash route ran the actual `CRITIC_PROMPT`, `CriticInput`, `Critique`, `ModelRouter`, and `ChatProvider` with synthetic source facts. The snapshot stated that 林舟 was 19; the draft said 20. Under `timeout=20`, `max_output_tokens=2048`, `max_retries=0`, and `deepseek_thinking=disabled`, the response passed the production `Critique` schema, chose `revise`, scored continuity **1/5**, cited the precise age conflict, and included restoring age 19 in `must_change`. The same probe's separate StoryBible call is recorded in ZEN-39's report; together they used 1,160 input and 1,819 output tokens over 12.318 seconds of model latency with no configured price estimate.

This checks a single domain critic decision after the ZEN-106 route fix. The synthetic chapter was deliberately short and was not submitted to the full Writer → verifier → Critic → Rewrite Harness or Feishu persistence path. It does not establish repeated continuity detection, final prose quality, human revision rate, or production latency. The PR stays draft pending those end-to-end and deployment checks.

## 2026-09-30 live DeepSeek and Feishu acceptance finding

The authorized synthetic test Base had the 18 additive ChapterVersions fields installed. The backend application identity then created, read, partially updated and deleted a ChapterVersion row; integer `chapter_no` and prose round-tripped. A separate RevisionTasks schema check is recorded in ZEN-41. These temporary schema-probe rows were deleted.

A production-service run against DeepSeek Flash and that Base generated a StoryBible, approved its exact Artifact into StoryState v2, generated an eligible ChapterBrief, then wrote a first-chapter draft. The Writer succeeded and persisted 3,136 characters of prose, but `verify_writer` failed. Read-only inspection of the persisted draft before cleanup showed that the model had copied IDs from nested planning/brief content instead of the exact chapter context and eligible brief Artifact IDs. The deterministic verifier correctly stopped the run before a ChapterVersion became reviewable. The run therefore **does not count as chapter-loop acceptance**. Its synthetic records were cleaned: 1 ApprovalEvent, 10 Traces, 10 StepRuns, 3 PipelineRuns, 2 StoryStates, 8 Artifacts and 1 Book; no ChapterVersion had been created. The failed run took 1,550.97 seconds.

The Writer and Rewrite inputs now each contain both required IDs as explicit top-level fields, and prompt versions `chapter-writer-v2` and `chapter-rewrite-v2` direct the model to copy those fields verbatim instead of nested IDs. A focused regression checks the actual messages sent to both routes and the distinction from the planning snapshot. All 13 chapter-loop tests passed. The full offline backend suite passed **363 tests**, with 9 credentialed tests deselected and approximately **91%** statement coverage. A separate real DeepSeek Flash prompt smoke check returned schema-valid first-chapter prose of 1,255 characters with both exact IDs, using 463 input and 953 output tokens over 6.555 seconds of model latency. It checks one model response, not the full persisted chapter path. The PR remains draft until that path is rerun and exact-head CI passes.

## Follow-up: bind source IDs outside model prose

A second full DeepSeek Flash plus Feishu attempt confirmed that the v2 Writer prompt fixed the first draft: its 4,205-character prose had both exact IDs, `verify_writer` passed, a candidate ChapterVersion was persisted, and the structured Critic returned `revise` with five required changes. The model's 5,120-character Rewrite had the exact brief ID but again copied a nested planning snapshot ID. The rewrite verifier stopped the run before selection or editorial review. This is a second **failed full-loop acceptance**, not a completed chapter. All temporary rows were removed: 1 ApprovalEvent, 14 Traces, 10 StepRuns, 1 candidate ChapterVersion, 3 PipelineRuns, 2 StoryStates, 12 Artifacts and 1 Book. Total elapsed time including cleanup was 1,643.77 seconds.

The correction moves source binding out of model-generated metadata. `chapter-writer-v3` and `chapter-rewrite-v3` request chapter number, title and prose. Each validated model response is preserved as a `ChapterModelResponse` Artifact, including any extra echoed fields. A deterministic binder creates the immutable `ChapterDraft` or `ChapterRewriteDraft` with the exact chapter snapshot and brief IDs from the frozen run, and links the model response as a source. The existing verifier still checks chapter number, those bound IDs, prose length and literal forbidden rules before a ChapterVersion can be materialized. A model-echoed wrong ID is retained as evidence and cannot change canonical provenance. The Critic still evaluates the initial verified version; a rewritten version retains that report as its trigger and receives its own deterministic verification.

The focused chapter suite passes **14 tests**, including wrong nested IDs on both Writer and Rewrite. The full offline backend suite passes **364 tests**, with 9 credentialed tests deselected and approximately **91%** statement coverage. Two small real DeepSeek Flash calls passed the new `ModelDraft` schema: Writer returned 1,605 characters (349 input/1,177 output tokens, 7.582 seconds model latency), and Rewrite returned 1,605 characters (1,551 input/1,177 output tokens, 4.599 seconds). The local Python environment lacks Ruff; exact-head CI must verify lint. Full Feishu chapter, human revision and final-lock acceptance remains pending after this fix, so the PR stays draft.

The binder's materialization path additionally checks that the stored model response belongs to the same run, generating step, route, prompt, chapter snapshot and brief, and that the bound draft contains exactly its validated prose plus canonical IDs. `ChapterVersions.prompt_version` records the Writer/Rewrite model prompt version rather than the binder's deterministic prompt. Focused tests cover both projections; the complete persisted rerun is still pending.
