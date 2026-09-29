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
