# ZEN-41 — Chapter review desk delivery record

## Goal and delivery scope

- [Linear ZEN-41](https://linear.app/zenhungyep/issue/ZEN-41/build-chapter-review-desk-with-selective-approval-and-final-lock) / [GitHub issue #14](https://github.com/autism-ip/novelops-agent-harness/issues/14).
- One draft PR for this issue, stacked on [ZEN-40 PR #36](https://github.com/autism-ip/novelops-agent-harness/pull/36), branch `codex/zen-41-chapter-review-desk` targeting `codex/zen-40-chapter-loop`. Merge order remains the upstream stack, then ZEN-40, then ZEN-41.
- Adds the book and chapter review desk, exact editorial APIs, persisted RevisionTasks, selective human gates, historical evidence, and final lock. The established Impeccable layout uses a desktop content/decision split, mobile stacking, rounded cards and restrained interaction transitions.

## Implementation and decisions

- `backend/app/chapter_loop.py` freezes first-N and low Critic score review policy in each run, exposes an exact review state, and validates run, version, Artifact and gate version before editorial commands. Routine passes complete automatically. Gated passes await an editor. Generic workflow step decisions cannot bypass chapter-specific version checks.
- Approve/reject persist an idempotent ApprovalEvent and update the selected ChapterVersion; a constrained revision persists a deterministic RevisionTask with source version, source Artifact, frozen request and explicit `must_keep`, `must_change`, `do_not_change`, then enqueues a rewrite. Replays reuse exact commands; conflicting or stale commands fail. Final lock accepts a reviewed or approved current version and blocks later changes while old versions remain.
- The review endpoint returns the current StoryState, StoryBible, Brief and snapshot plus every version's own Critic report and deterministic verification Artifact. The UI changes prose, report, verification and source references together when an older version is selected; current run planning and usage are labeled separately. Historical versions are read-only. A local session storage recovery card retains uncertain commands for exact replay.
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

Desktop evidence: [review and final lock](assets/zen41-review-desktop.png). Mobile evidence: [reachable review controls](assets/zen41-review-mobile-actions.png). These are synthetic data from the local fixture, not real Feishu or model output.

## Verified facts, judgment and open limits

**Verified facts:** The tests and local browser paths above passed. Current upstream PR #36 is open, draft, and based on PR #35; its head when this report was prepared was `fbd3a666485a906472a3457ad96dbf953849b7ff`. The ZEN-41 issue was open/Todo with no explicit Linear blocker relation.

**Engineering judgment:** The API keeps the exact version contract at the server boundary, where a stale or duplicate browser action can otherwise mutate the wrong chapter. The first-N and dimension threshold policy gives a selective human gate while allowing routine passes to proceed.

**Unverified assumptions:** Production Feishu tables have or will receive the additive RevisionTasks fields and sufficient read/write scopes. Real model quality, production pricing/latency and Bitable field limits have not been validated by the synthetic fixture.

**Risks and next actions:** Keep the PR draft while stacked dependencies and live Feishu acceptance remain. Check the PR's own exact-head CI and all review sources after pushing; address any valid findings on this branch. Configure the documented policy values and validate one gated plus one routine run against production credentials before readiness for merge.

## Reusable skill assessment

The `issue-pr-delivery` workflow remains suitable: exact issue/PR mapping, immediate dependency base, commit-specific CI and a durable acceptance report prevented a passing descendant from being mistaken for an accepted production feature. No skill text change was required for this issue.
