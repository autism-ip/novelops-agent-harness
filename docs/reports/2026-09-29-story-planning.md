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

Review status at the report check: no submitted reviews, discussion comments, or inline threads on PR #35. No review finding needed a code disposition. The PR remains draft because its base PR #34 and upstream stack remain under review.

Screenshots: [desktop major approval](assets/zen-39-storybible-major-desktop.png), [phone major approval](assets/zen-39-storybible-major-mobile.png), [phone regenerated brief](assets/zen-39-chapter-brief-mobile.png).

## Findings, limits, and next dependency

The first Book layout pushed approval controls beyond the initial viewport. A compact premise/protagonist preview and expandable full Bible resolved that in the tested desktop and phone layouts. Story planning workflow statuses no longer disable unrelated hotspot actions. The Book bootstrap replay now accepts the expected later StoryState pointer while preserving the original bootstrap identity.

ZEN-40 chapter generation must consume the policy-eligible ChapterBrief and immutable snapshot boundary. This PR does not claim chapter prose generation or live Feishu/model acceptance. The existing `issue-pr-delivery` skill remains useful for issue-to-PR tracing; no new reusable skill is warranted from these domain-specific contracts.

Verified facts are the local/CI gates, synthetic browser actions, exact artifact refs, and current review inventory above. The engineering judgment is that the API and Book UX are ready for human code review in the stacked branch. Unverified assumptions are production model output quality, Feishu table permissions and write semantics, and runtime behavior after deployment. The remaining technical debt is live integration acceptance, tracked with the existing Feishu/provider dependency rather than hidden by fixture results.
