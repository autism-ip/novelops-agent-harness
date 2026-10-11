# ZEN-41 production composition and real-provider acceptance — 2026-10-12

## Requirement and delivery

[ZEN-41](https://linear.app/zenhungyep/issue/ZEN-41/build-chapter-review-desk-with-selective-approval-and-final-lock) requires an editor to inspect exact chapter sources and versions, request constrained revision, approve or reject, and lock a verified final version. Delivery remains [PR #37](https://github.com/autism-ip/novelops-agent-harness/pull/37), against the existing ZEN-40 branch. The issue remains In Review. No merge or Done transition occurred.

Production source: `4e33cd5d7058a5b52b9e8d30731a202fa15e68e5`.

## Verified defect and fix

The production `build_runtime` registered ChapterVersions but omitted RevisionTasks. The review service reads RevisionTasks even before a revision exists, so the deployed storage boundary could raise `KeyError` despite fixture-based chapter tests passing. Missing revision-table configuration was also not caught at startup.

Two requirement-oriented regressions were added before the fix. Both failed: absent configuration did not raise, and configured revision history raised `KeyError`. The fix adds RevisionTasks to the chapter runtime repositories. The tests now prove that missing configuration fails startup and that configured reads use the physical table ID with the expected domain filter. The complete chapter-review suite passed: 23 tests. All offline backend tests passed: 491; 10 opt-in integration cases were deselected. Ruff and `git diff --check` passed. No assertions or quality thresholds were lowered.

Changed modules: `backend/app/runtime.py`, `backend/tests/test_chapter_review.py`, backend and test documentation. Frontend source was unchanged in this repair.

## Coverage and completion limit

All app sources remain in the measurement scope. Current backend results:

| Metric | Result |
|---|---:|
| Statements / lines | 3964 / 4254 = 93.18% |
| Branches | 914 / 1126 = 81.17% |
| Raw named function entries | 401 / 419 = 95.70% |
| Lambdas | 11 / 11 = 100% |

The coverage.py combined display is 90.67%; it is not statement coverage. Its existing default exclusion reports 11 source lines around seven Protocol declarations. The raw function-entry catalog keeps those declarations in its denominator. No new exclusions were added. The prior frontend report measured 91.07% statements, 93.43% lines, 88.70% functions and 90.05% branches with 216 passing tests; frontend tests were not rerun for this backend-only change.

**The user's 100% coverage requirement is not met. The full issue and project goal are not complete.**

## Real-provider preflight

Target is the previously authorized synthetic [Feishu test Base](https://fcnaul7kb1kf.feishu.cn/base/T8I6buCMoaiLB6srVBrc9i2jnph). CLI and MCP availability was checked first: gh and lark-cli exist; Linear/GitHub MCP exist; no Feishu or DeepSeek MCP and no DeepSeek CLI were discovered. The production app-identity adapter was used under the user's earlier authorization. No credentials were copied into the worktree or report.

The user-identity CLI read lacked `base:app:read`; no reauthorization or identity change was attempted. The intended app-identity runtime read succeeded. The Base was missing Hotspots, HotspotAnalyses, TitleCandidates and CoverPlans. Those four schema tables were created inside the already-authorized synthetic Base and retained as acceptance resources. Existing tables were unchanged. Each table's fields were independently read back; the final 13 runtime collections have no missing mapped fields. Their IDs and types are retained in the JSON evidence.

## First real chain attempt: observed timeout, safe stop

This used actual FastAPI domain APIs, the production runtime composition and synchronous production `HarnessKernel.tick`, real app-identity Feishu storage and real DeepSeek calls. It did not use pre-generated model fixtures or replace the storage/model core. It was not a browser, deployed server or background-scheduler test.

The manual synthetic hotspot was persisted and its workflow completed. A research run was reserved. Its only model attempt timed out at the configured 15-second budget (trace latency 15353.252 ms). The research step failed and dependent risk/selection/commit steps were cancelled. No opportunity artifact, chapter, or final lock was produced. Tokens and estimated cost remain null; an unknown billed outcome is not reported as zero.

The complete failed run lasted 263.434 seconds including evidence reads and cleanup. It made 189 Feishu requests: 134 POST, 24 GET, 18 PUT and 13 DELETE. POST includes read-only business-key searches, so this is not a mutation count. The research scheduler tick took 91.819 seconds, exposing substantial remote storage overhead beyond the bounded model call; no acceptable end-to-end latency budget is claimed.

All 13 attempted business IDs were journaled before writes. Cleanup deleted only those IDs. A separate client then checked every affected collection: no residual records; no cleanup errors. The four schema tables remain intentionally retained.

## Connectivity and ongoing chain

A 64-output-token connectivity diagnostic succeeded using the same production ChatProvider: DeepSeek returned `{"ok":true}`, 38 input tokens, 5 output tokens, finish reason `stop`, in 0.990 seconds. This only proves connectivity and usable credentials, not generation quality or issue acceptance. An earlier diagnostic had a probe-side AttributeError reading `Completion.text` instead of `content`; its result is retained separately and was not reported as a provider timeout.

A new acceptance ID now runs the same full chain with all route timeouts set to 25 seconds, within the existing application ceiling and with zero model retries. The schemas, artifacts, gates, chapter constraints and requested workflow are unchanged. This is an explicit test configuration delta, not a silent claim that the original 15-second route succeeded. At publication, the result is still pending; no full-generation, constrained-rewrite or final-lock success is claimed.

Current routes have no configured token prices. Real usage will remain distinguishable from any calculation using [official DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/). The diagnostic's token count is not a billed-cost statement.

## Review, security and remaining work

The fresh all-13-PR audit found zero unresolved inline threads. The source repair is pushed to PR #37. Current-head CI status is recorded separately; green checks do not prove requirement achievement. Linear ZEN-105, ZEN-106 and ZEN-41 were reread with relationships and remain In Review, linked to their original PRs.

Verified safeguards: fixed synthetic Base pin, explicit application identity, authentication rejection before capability access, no secret output, pre-write ownership journal, prohibition on modifying unrelated records, cancellation of dependent steps after model failure, independent scoped cleanup. No ACL grant, token login, dependency upgrade, second database or message to another person was performed.

Still unverified or incomplete: real full generation/rewrite/review/final-lock chain, independent semantic quality and continuity assessment, routine automatic-pass policy under real providers, deployed frontend/backend authorization and schema parity, real polling/timeout/latency/cost budgets, and all-source 100% coverage. The measured Feishu overhead is an active engineering risk, not dismissed as fixture noise.

Reusable workflow assessment: the existing issue-pr-delivery and lark-base skills were reused. Production-composition preflight, exact Base pinning, before-write domain-ID journaling and independent cleanup are stable reusable steps; the new live chain is still being validated, so no unproven new skill is claimed. The existing issue-pr-delivery workflow should preserve the distinction between runtime requirement events and CI evidence.
